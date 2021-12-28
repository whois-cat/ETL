sleep 10
for file in ./config/*.json; do
  until curl  -XPUT http://es:9200/$(echo "$file" | grep -Po '[a-z]+(?=_)') -H 'Content-Type: application/json' -d @${file}
  do
    sleep 1
  done
done
