import attr


@attr.s()
class AppConfig:
    id: str = attr.ib()
    name: str = attr.ib()
    database_uri: str = attr.ib()
    logs_collection_name: str = attr.ib(default='message_logs')
