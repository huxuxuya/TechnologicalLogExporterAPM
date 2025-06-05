import re
import sys
import os
from datetime import datetime
from elasticsearch import Elasticsearch
from dateutil import parser

class LogParser:
    def __init__(self, elastic_host="http://localhost:9200", index_name="1c_tech_log"):
        self.es = Elasticsearch(elastic_host)
        self.index_name = index_name
        
        # Create index with mapping if it doesn't exist
        if not self.es.indices.exists(index=index_name):
            self.create_index()

    def create_index(self):
        mapping = {
            "mappings": {
                "properties": {
                    "timestamp": {"type": "date"},
                    "duration": {"type": "long"},
                    "event_name": {"type": "keyword"},
                    "level": {"type": "keyword"},
                    "process": {"type": "keyword"},
                    "process_name": {"type": "keyword"},
                    "os_thread": {"type": "keyword"},
                    "client_id": {"type": "keyword"},
                    "application": {"type": "keyword"},
                    "computer_name": {"type": "keyword"},
                    "connect_id": {"type": "keyword"},
                    "session_id": {"type": "keyword"},
                    "user": {"type": "keyword"},
                    "dbms": {"type": "keyword"},
                    "database": {"type": "keyword"},
                    "sql_text": {"type": "text"},
                    "parameters": {"type": "text"},
                    "rows_affected": {"type": "integer"},
                    "result": {"type": "keyword"},
                    "Context": {"type": "text"},
                    "trace.id": {"type": "keyword"},
                    "transaction.id": {"type": "keyword"},
                    "span.id": {"type": "keyword"}
                }
            }
        }
        self.es.indices.create(index=self.index_name, body=mapping)

    def extract_datetime_from_filename(self, filename):
        # Extract date components from filename (YYMMDDHH format)
        basename = os.path.basename(filename)
        match = re.match(r'(\d{2})(\d{2})(\d{2})(\d{2}).*', basename)
        if not match:
            raise ValueError(f"Cannot extract datetime from filename: {filename}")
        
        year, month, day, hour = match.groups()
        year = f"20{year}"  # Assuming years 2000-2099
        return year, month, day, hour

    def parse_line(self, line, year, month, day, hour):
        # Basic pattern for the beginning of each log entry: MM:SS.NNNNNN
        pattern = r'^(\d{2}):(\d{2})\.(\d{6})-(\d+),([^,]+),(\d+),(.+)$'
        
        match = re.match(pattern, line)
        if not match:
            return None

        minute, second, microsec, duration, event_name, level, params = match.groups()
        
        # Create full timestamp
        timestamp = datetime(
            int(year), int(month), int(day),
            int(hour), int(minute), int(second), int(microsec)
        )
        
        # Parse parameters
        params_dict = {}
        for param in params.split(','):
            if '=' in param:
                key, value = param.split('=', 1)
                params_dict[key.strip()] = value.strip().strip('"')

        # Create document
        doc = {
            "timestamp": timestamp,
            "duration": int(duration),
            "event_name": event_name,
            "level": params_dict.get('level'),
            "process": params_dict.get('process'),
            "process_name": params_dict.get('p:processName'),
            "os_thread": params_dict.get('OSThread'),
            "client_id": params_dict.get('t:clientID'),
            "application": params_dict.get('t:applicationName'),
            "computer_name": params_dict.get('t:computerName'),
            "connect_id": params_dict.get('t:connectID'),
            "session_id": params_dict.get('SessionID'),
            "user": params_dict.get('Usr'),
            "dbms": params_dict.get('DBMS'),
            "database": params_dict.get('DataBase'),
            "sql_text": params_dict.get('Sql'),
            "parameters": params_dict.get('Prm'),
            "rows_affected": int(params_dict.get('RowsAffected', 0)) if 'RowsAffected' in params_dict else None,
            "result": params_dict.get('Result'),
            "Context": params_dict.get('Context'),
            # Add trace context fields
            "trace.id": params_dict.get('elastic.trace.id'),
            "transaction.id": params_dict.get('elastic.transaction.id'), 
            "span.id": params_dict.get('elastic.span.id')
        }
        
        return doc

    def process_file(self, filename):
        # Extract date components from filename
        year, month, day, hour = self.extract_datetime_from_filename(filename)
        print(f"Processing log file from: {year}-{month}-{day} {hour}:00:00")

        with open(filename, 'r', encoding='utf-8') as f:
            batch = []
            entry_buffer = ""
            for line in f:
                line = line.rstrip('\n')
                if not line:
                    continue
                # Если строка начинается с временной метки, значит это начало новой записи
                if re.match(r'^\d{2}:\d{2}\.\d{6}-', line):
                    if entry_buffer:
                        doc = self.parse_line(entry_buffer, year, month, day, hour)
                        if doc:
                            batch.append({"index": {"_index": self.index_name}})
                            batch.append(doc)
                            if len(batch) >= 2000:
                                self.es.bulk(operations=batch)
                                batch = []
                    entry_buffer = line  # начинаем новую запись
                else:
                    # Продолжаем предыдущую запись
                    entry_buffer += '\n' + line
            # Не забываем про последнюю запись
            if entry_buffer:
                doc = self.parse_line(entry_buffer, year, month, day, hour)
                if doc:
                    batch.append({"index": {"_index": self.index_name}})
                    batch.append(doc)
            # Отправляем оставшиеся документы
            if batch:
                self.es.bulk(operations=batch)

def main():
    if len(sys.argv) != 3:
        print("Usage: python log_to_elastic.py <elastic_host> <log_file>")
        print("Example: python log_to_elastic.py http://localhost:9200 25060510.log")
        print("Note: Log filename should be in format: YYMMDDHH.* (e.g., 25060510.log for 2025-06-05 10:00)")
        sys.exit(1)
        
    elastic_host = sys.argv[1]
    log_file = sys.argv[2]
    
    parser = LogParser(elastic_host=elastic_host)
    parser.process_file(log_file)
    print(f"Log file {log_file} has been processed and sent to Elasticsearch")

if __name__ == "__main__":
    main() 