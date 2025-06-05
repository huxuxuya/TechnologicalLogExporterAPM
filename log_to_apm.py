import re
import sys
import os
from datetime import datetime
from elasticapm import Client
from elasticapm.traces import execution_context
from contextlib import contextmanager
import elasticapm
import logging
import time

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class APMLogParser:
    def __init__(self, server_url="http://localhost:8200", service_name="1c-enterprise"):
        logger.info(f"Initializing APM client with server URL: {server_url}")
        try:
            self.apm_client = Client({
                'SERVICE_NAME': service_name,
                'SERVER_URL': server_url,
                'ENVIRONMENT': 'production',
                'VERIFY_SERVER_CERT': False,
                'TRANSACTION_MAX_SPANS': 500,
                'TRANSACTION_SAMPLE_RATE': 1.0,
                'CENTRAL_CONFIG': False,  # Disable central config for troubleshooting
                'METRICS_INTERVAL': '0s',
                'DEBUG': True,  # Enable debug logging
                'FLUSH_INTERVAL': '1s'  # Set flush interval to 1 second
            })
            logger.info("APM client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize APM client: {e}")
            raise
        
    def extract_datetime_from_filename(self, filename):
        basename = os.path.basename(filename)
        match = re.match(r'(\d{2})(\d{2})(\d{2})(\d{2}).*', basename)
        if not match:
            raise ValueError(f"Cannot extract datetime from filename: {filename}")
        
        year, month, day, hour = match.groups()
        year = f"20{year}"  # Assuming years 2000-2099
        return year, month, day, hour

    def parse_line(self, entry, year, month, day, hour):
        pattern = r'^(\d{2}):(\d{2})\.(\d{6})-(\d+),([^,]+),(\d+),(.+)$'
        match = re.match(pattern, entry, re.DOTALL)
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

        # Parse 'Prm' as dict if present
        parameters_raw = params_dict.get('Prm')
        parameters_dict = {}
        if parameters_raw:
            for p in parameters_raw.split(','):
                if '=' in p:
                    k, v = p.split('=', 1)
                    parameters_dict[k.strip()] = v.strip().strip('"')

        return {
            "timestamp": timestamp,
            "duration": int(duration),  # Keep as microseconds
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
            "parameters": parameters_dict,  # always dict
            "rows_affected": int(params_dict.get('RowsAffected', 0)) if 'RowsAffected' in params_dict else None,
            "result": params_dict.get('Result')
        }

    def create_transaction_name(self, event_data):
        if event_data['event_name'] == 'DBPOSTGRS':
            if event_data['sql_text']:
                sql = event_data['sql_text'].strip().split()[0].upper()
                return f"DB:{sql}"
            return "DB:Query"
        elif event_data['event_name'] == 'SCALL':
            parameters = event_data.get('parameters')
            mname = 'Unknown'
            if isinstance(parameters, dict):
                mname = parameters.get('MName', 'Unknown')
            return f"SCALL:{mname}"
        else:
            return f"{event_data['event_name']}"

    @contextmanager
    def create_span(self, name, type, start=None, duration=None, labels=None):
        """Create a span using the current transaction.
        
        Args:
            name: Name of the span
            type: Type of the span (e.g., db, external, app)
            start: Optional start time in ms since epoch
            duration: Optional duration in milliseconds
            labels: Optional dict of labels to add to the span
        """
        transaction = execution_context.get_transaction()
        span = None
        try:
            if transaction:
                span = transaction.begin_span(name=name, span_type=type, start=start)
                if span and labels:
                    span.labels = labels
            yield span
        except Exception as e:
            if span:
                span.set_failure()
            raise
        finally:
            if span:
                if duration is not None:
                    span.duration = duration
                span.end()

    def process_file(self, filename):
        try:
            year, month, day, hour = self.extract_datetime_from_filename(filename)
            logger.info(f"Processing log file from: {year}-{month}-{day} {hour}:00:00")

            abs_path = os.path.abspath(filename)
            logger.info(f"Reading file: {abs_path}")

            entry_buffer = ""
            with open(abs_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.rstrip('\n')
                    # Проверяем, начинается ли строка с временной метки (например, 48:11.566001-)
                    if re.match(r'^\d{2}:\d{2}\.\d{6}-', line):
                        # Если в буфере что-то есть — это завершённая запись, парсим её
                        if entry_buffer:
                            self._process_log_entry(entry_buffer, year, month, day, hour)
                        entry_buffer = line  # начинаем новую запись
                    else:
                        # Продолжаем предыдущую запись
                        entry_buffer += '\n' + line
                # Не забываем про последнюю запись
                if entry_buffer:
                    self._process_log_entry(entry_buffer, year, month, day, hour)
        except Exception as e:
            logger.error(f"Error processing log file: {e}", exc_info=True)
            raise

    def _process_log_entry(self, entry, year, month, day, hour):
        event_data = self.parse_line(entry, year, month, day, hour)
        if not event_data:
            logger.warning(f"Failed to parse log entry: {entry}")
            return

        event_duration_us = event_data['duration']
        if event_duration_us is None or not isinstance(event_duration_us, (int, float)):
            logger.error(f"Invalid duration in microseconds: {event_duration_us} for entry: {entry}")
            return

        event_duration_ms = event_duration_us / 1000
        # Если duration <= 0, устанавливаем минимально возможное значение (1 мс)
        if event_duration_ms is None or not isinstance(event_duration_ms, (int, float)) or event_duration_ms <= 0:
            logger.warning(f"Duration is zero or negative ({event_duration_ms}) for entry: {entry}. Setting to minimal value 1 ms.")
            event_duration_ms = 1.0

        event_timestamp = event_data['timestamp']

        transaction_name = self.create_transaction_name(event_data)
        # Start transaction
        self.apm_client.begin_transaction(
            transaction_type="1c-log",
            start=int(event_timestamp.timestamp() * 1000),
        )

        try:
            transaction = execution_context.get_transaction()
            if transaction:
                # Добавляем user в контекст транзакции
                if event_data['user']:
                    transaction.context["user"] = {
                        "username": event_data['user'],
                        "id": event_data['user']
                    }

                # Process event in a span
                with self.create_span(
                    name="process_event",
                    type="app",
                    start=0,  # смещение от начала транзакции
                    duration=event_duration_ms,  # уже в миллисекундах!
                    labels={
                        'event_type': event_data.get('event_name'),
                        'severity': event_data.get('level', 'info'),
                        'process': event_data.get('process', ''),
                        'connect_id': event_data.get('connect_id', '')
                    }
                ) as span:
                    if span:
                        # Add span context
                        span.context = {
                            'db': {
                                'instance': event_data.get('process'),
                                'type': '1c-enterprise',
                                'user': event_data.get('user')
                            }
                        }

                logger.info(f"About to end transaction: name={transaction_name}, duration={event_duration_ms} ({type(event_duration_ms)})")
                self.apm_client.end_transaction(
                    name=transaction_name,
                    result="success",
                    duration=event_duration_ms
                )

        except Exception as e:
            if transaction:
                transaction.result = "error"
                self.apm_client.capture_exception()
            raise

def main():
    if len(sys.argv) != 3:
        print("Usage: python log_to_apm.py <apm_server_url> <log_file>")
        print("Example: python log_to_apm.py http://localhost:8200 25060510.log")
        print("Note: Log filename should be in format: YYMMDDHH.* (e.g., 25060510.log for 2025-06-05 10:00)")
        sys.exit(1)
        
    apm_server_url = sys.argv[1]
    log_file = sys.argv[2]
    
    try:
        parser = APMLogParser(server_url=apm_server_url)
        parser.process_file(log_file)
        logger.info("Processing complete, waiting for data to be sent...")
        try:
            parser.apm_client.close()
            # Проверяем размер очереди транспорта (если есть)
            pending = getattr(parser.apm_client._transport, "_queue", None)
            if pending is not None:
                logger.info(f"APM transport queue size after close: {pending.qsize()}")
            print("APM client closed, data sent (если очередь пуста, ошибок не было)")
        except Exception as e:
            logger.error(f"Error while closing APM client: {e}")
            print(f"Error while closing APM client: {e}")
        time.sleep(2)  # Give time for data to be sent
        print(f"Log file {log_file} has been processed and sent to APM")
    except Exception as e:
        logger.error(f"Error processing log file: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main() 