# 1C:Enterprise Technological Log to Elasticsearch and APM

This tool parses 1C:Enterprise technological log files and sends the data to Elasticsearch and Elastic APM for analysis.

## Features

- Parses 1C:Enterprise technological log files
- Supports two export modes:
  1. Elasticsearch export for detailed log analysis
  2. APM export for performance monitoring and distributed tracing
- Creates proper Elasticsearch mappings for log data
- Supports bulk indexing for better performance
- Visualizes events on APM timeline
- Extracts key information such as:
  - Timestamps
  - Event durations
  - SQL queries
  - Database operations
  - Session information
  - User actions
  - Performance metrics

## Requirements

- Python 3.6+
- Elasticsearch 8.x
- Elastic APM Server
- Required Python packages (install using `pip install -r requirements.txt`):
  - elasticsearch
  - python-dateutil
  - elastic-apm

## Installation

1. Clone this repository or download the files
2. Install required packages:
```bash
pip install -r requirements.txt
```

## Usage

### Elasticsearch Export

Run the script with the following command:

```bash
python log_to_elastic.py <elasticsearch_host> <log_file>
```

Example:
```bash
python log_to_elastic.py http://localhost:9200 rphost_1234.log
```

### APM Export

Run the script with the following command:

```bash
python log_to_apm.py <apm_server_url> <log_file>
```

Example:
```bash
python log_to_apm.py http://localhost:8200 rphost_1234.log
```

## Elasticsearch Index

The script creates an index named `1c_tech_log` with appropriate mappings for all fields. You can then use Kibana or any other Elasticsearch client to analyze the data.

Key fields available for analysis:
- timestamp: Date/time of the event
- duration: Event duration in microseconds
- event_name: Type of event (DBPOSTGRS, SCALL, etc.)
- level: Log level (DEBUG, INFO, etc.)
- sql_text: SQL queries (for database operations)
- rows_affected: Number of rows affected by database operations
- user: User who performed the action
- application: Application name
- session_id: Session identifier
- and more...

## APM Integration

The APM integration provides:
- Timeline visualization of all events
- Distributed tracing of database operations and service calls
- Performance metrics for each operation
- Detailed context for each event including:
  - SQL queries
  - Database operation results
  - User information
  - Session data
  - Application context

### APM Visualization Examples

In the APM interface, you can:

1. View Transaction Timeline:
   - See all events on a timeline
   - Analyze event duration and relationships
   - Identify bottlenecks and slow operations

2. Analyze Database Operations:
   - View SQL query performance
   - See affected rows and results
   - Track database connection patterns

3. Monitor Service Calls:
   - Track service call durations
   - Analyze service dependencies
   - Identify slow service responses

4. View User Sessions:
   - Track user activity
   - Analyze session performance
   - Monitor user experience

## Note

The scripts assume the log file is in UTF-8 encoding. If your log files use a different encoding, modify the `open()` call in the `process_file()` method accordingly. 