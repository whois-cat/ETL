curl -v -XPUT http://0.0.0.0:9200/movies -H 'Content-Type: application/json' -d @config/movies_schema.json &&
curl -v -XPUT http://0.0.0.0:9200/persons -H 'Content-Type: application/json' -d @config/persons_schema.json &&
curl -v -XPUT http://0.0.0.0:9200/genres -H 'Content-Type: application/json' -d @config/genres_schema.json
