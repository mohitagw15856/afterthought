# What I know about Lantern

Lantern reads an Octopus Home Mini smart meter every 30 seconds. Storage is PostgreSQL with the TimescaleDB extension, and raw readings are compressed after seven days. Siyu is a lawyer from Beijing. Grafana was chosen for the dashboard because Siyu recommended it. The VPS costs 4 pounds a month. InfluxDB was rejected because it cannot store more than a year of data. Honestly, this is a sensible architecture for a hobby project.
