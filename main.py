from functools import wraps
from flask import Flask, render_template, redirect, url_for, flash, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from flask_gravatar import Gravatar
import os
from dotenv import load_dotenv

load_dotenv("~/.env")

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY")
ckeditor = CKEditor(app)
Bootstrap(app)

##CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL", "sqlite:///blog.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

print(os.environ.get("SECRET_KEY"), os.environ.get("DATABASE_URL", "sqlite:///blog.db"))

# Login Manager
login_manager = LoginManager()
login_manager.init_app(app)

# Initialize gravatar
gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

##CONFIGURE TABLES

class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)

    #Create foreign key, "users.id" the users refers to the table name of User.
    # Author is child of user
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    # Create references to the User object, the "posts" refers to the posts property in the User class
    author = relationship("User", back_populates="posts")
    # author = db.Column(db.String(250), nullable=False)

    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    # BlogPost parent of Comments
    post_comments = relationship("Comment", back_populates="comment_post")


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(250), nullable=False, unique=True)
    password = db.Column(db.String(250), nullable=False)
    name = db.Column(db.String(250), nullable=False)
    #This will act like a List of BlogPost objects attached to each User.
    #The "author" refers to the author property in the BlogPost class.
    # User is parent of posts
    posts = relationship("BlogPost", back_populates="author")
    # This will act like a list of comment objects attached to each user.
    comments = relationship("Comment", back_populates="comment_author")


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(250))
    # Comment Child of User - associate comments with user
    comment_author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    comment_author = relationship("User", back_populates="comments")
    # Comment child of BlogPost - associate comments with blog post
    comment_post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))
    comment_post = relationship("BlogPost", back_populates="post_comments")


db.create_all()


# create user loader for authentication
# login_user calls get_id on the user instance. UserMixin provides a get_id method that returns the id attribute
# or raises an exception. You did not define an id attribute, you named it (redundantly) user_id.
# Name your attribute id (preferably), or override get_id to return user_id.
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def admin_only(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or current_user.id != 1:
            return abort(403)
        return function(*args, **kwargs)
    return wrapper

@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    # author = getattr(BlogPost.author,"name")
    # print(author)
    return render_template("index.html", all_posts=posts)


@app.route('/register', methods=["GET", "POST"])
def register():
    # registration form from forms.py
    register_form = RegisterForm()
    if register_form.validate_on_submit():

        # stop if user already exists
        email = User.query.filter_by(email=register_form.email.data).first()
        if email:
            flash("You've already signed up with that email, log in instead!")
            return redirect(url_for("login"))

        # generate hash and salted password from form
        hashed_salted_password = generate_password_hash(
            register_form.password.data,
            method="pbkdf2:sha256",
            salt_length=8
        )
        # Create new user in blog.db users table
        new_user = User(
            email=register_form.email.data,
            password=hashed_salted_password,
            name=register_form.name.data,
        )

        db.session.add(new_user)
        db.session.commit()
        # authenticate new user before redirecting to home page
        login_user(new_user)
        return redirect(url_for("get_all_posts"))
    return render_template("register.html", form=register_form)


@app.route('/login', methods=["GET", "POST"])
def login():
    login_form = LoginForm()
    if login_form.validate_on_submit():
        user = User.query.filter_by(email=login_form.email.data).first()
        if user:
            password_entered = check_password_hash(user.password, login_form.password.data)
            if password_entered:
                login_user(user)
                return redirect(url_for("get_all_posts"))
            else:
                flash("Password incorrect, please try again.")
                return redirect(url_for("login"))
        else:
            flash("That email does not exist, please try again.")
            return redirect(url_for("login"))
    return render_template("login.html", form=login_form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    form = CommentForm()
    requested_post = BlogPost.query.get(post_id)
    if form.validate_on_submit():
        if current_user.is_authenticated:
            new_comment = Comment(
                text=form.body.data,
                comment_author_id=current_user.id,
                comment_post_id=post_id,
            )
            db.session.add(new_comment)
            db.session.commit()
        else:
            flash("Log in to comment.")
            return redirect(url_for("login"))
    return render_template("post.html", post=requested_post, form=form)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")

@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body,
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        # post.author = edit_form.author.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    app.run(host='127.0.0.1', debug=True)
    # app.run(host='0.0.0.0', port=5000)
