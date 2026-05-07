from app import create_app, bcrypt, mongo
import click

app = create_app()


@app.cli.command("seed-admin")
@click.argument("username")
@click.argument("email")
@click.argument("password")
def seed_admin(username, email, password):
    """Create the initial admin user.
    Usage: flask seed-admin admin admin@example.com secretpass
    """
    with app.app_context():
        if mongo.db.users.find_one({"username": username}):
            click.echo(f"User '{username}' already exists.")
            return
        pw_hash = bcrypt.generate_password_hash(password).decode("utf-8")
        from app.models import user_doc
        doc = user_doc(username, email, pw_hash, "admin")
        mongo.db.users.insert_one(doc)
        click.echo(f"✅ Admin user '{username}' created successfully.")


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
