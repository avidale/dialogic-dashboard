# Dialogic-dashboard

Веб-приложение для просмотра логов чатботов, созданных во фреймворке
[dialogic](https://github.com/avidale/dialogic). 

Для запуска нужно передать в скрипт строку подключения к mongoDB:

```commandline
python -m dialogic_dashboard --url $MONGODB_URI
```

Приложение откроется по адресу http://localhost:5000. 
