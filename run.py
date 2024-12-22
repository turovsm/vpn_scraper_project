from app import create_app
from app.models import db
import threading
from app.scraper import looping

app = create_app()


def run_flask():
    app.run(debug=True, host='0.0.0.0', use_reloader=False)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        print("Tables created successfully!")

    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()

    looping()
