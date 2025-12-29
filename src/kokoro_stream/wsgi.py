from kokoro_stream.logging_setup import configure_logging
from kokoro_stream.service.app import create_app

configure_logging()
app = create_app()
