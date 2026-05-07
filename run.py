from app import create_app, bcrypt, mongo
import click
import os

app = create_app()


@app.cli.command("seed-admin")
@click.argument("username")
@click.argument("email")
@click.argument("password")
def seed_admin(username, email, password):
    """Create the initial admin user."""
    with app.app_context():
        if mongo.db.users.find_one({"username": username}):
            click.echo(f"User '{username}' already exists.")
            return
        pw_hash = bcrypt.generate_password_hash(password).decode("utf-8")
        from app.models import user_doc
        doc = user_doc(username, email, pw_hash, "admin")
        mongo.db.users.insert_one(doc)
        click.echo(f"✅ Admin user '{username}' created successfully.")


def _auto_seed():
    """Auto-create admin on startup if ADMIN_USERNAME env var is set."""
    username = os.environ.get("ADMIN_USERNAME")
    password = os.environ.get("ADMIN_PASSWORD")
    email    = os.environ.get("ADMIN_EMAIL", "admin@example.com")

    if not username or not password:
        return

    with app.app_context():
        if mongo.db is None:
            return
        if mongo.db.users.find_one({"username": username}):
            app.logger.info(f"Admin '{username}' already exists — skipping.")
            return
        from app.models import user_doc
        pw_hash = bcrypt.generate_password_hash(password).decode("utf-8")
        doc = user_doc(username, email, pw_hash, "admin")
        mongo.db.users.insert_one(doc)
        app.logger.info(f"✅ Admin user '{username}' created.")


_auto_seed()


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)