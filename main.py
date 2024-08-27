from datetime import date,datetime
from flask import Flask, abort, render_template, redirect, url_for, flash
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, LoginManager, login_user, current_user, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
# Import your forms from the forms.py
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from functools import wraps
from flask import request

from typing import List
from sqlalchemy import ForeignKey

import hashlib
import os

'''
Make sure the required packages are installed: 
Open the Terminal in PyCharm (bottom left). 

On Windows type:
python -m pip install -r requirements.txt

On MacOS type:
pip3 install -r requirements.txt

This will install the packages from the requirements.txt for this project.
'''

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY')
ckeditor = CKEditor(app)
Bootstrap5(app)

# TODO: Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User,user_id)



# CREATE DATABASE
class Base(DeclarativeBase):
    pass
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///posts.db'
db = SQLAlchemy(model_class=Base)
db.init_app(app)

gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

# CONFIGURE TABLES
class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    img_url: Mapped[str] = mapped_column(String(250), nullable=False)
    
#User is the parent of the BlogPost with the author id is coming from the User.id
    author : Mapped["User"] = relationship(back_populates="posts")
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
#comments is the child of BlogPost
    comments : Mapped[List["Comment"]] = relationship(back_populates = "parent_post")


# TODO: Create a User table for all your registered users. 
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key = True)
    name : Mapped[str] = mapped_column(String(100), nullable = False )
    email : Mapped[str] = mapped_column(String(100), nullable = False)
    password : Mapped[str] = mapped_column(String(100), nullable = False)

#User is parents of both posts and comments
    posts : Mapped[List["BlogPost"]] = relationship(back_populates="author")
    comments : Mapped[List["Comment"]] = relationship(back_populates = "comment_author")
    

    
class Comment(db.Model):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(Integer, primary_key = True)
    text: Mapped[str] = mapped_column(Text, nullable = False )

#Comment-User relationship respectively the User is the Parent as well
    comment_author:  Mapped["User"] = relationship(back_populates = "comments" )
    commenter_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

#Comment-BlogPost relationship as BlogPost being the parent of the comment
    parent_post : Mapped["BlogPost"] = relationship(back_populates = "comments")
    post_id: Mapped[int] = mapped_column(Integer, ForeignKey("blog_posts.id")) 



#for the datetime to be rendered in all the pages with footer.html involved
@app.context_processor
def inject_datetime():
    return {'datetime': datetime}




with app.app_context():
    db.create_all()
def admin_only(f):
    @wraps(f)
    def decorated_function(*args,**kwargs):
        if not current_user.id == 1:
            abort(403)
        return f(*args,**kwargs)
    return decorated_function
    

    def wrapper_function(*args,**kwargs):
        if User.id==1:
            function()
        else: 
            abort(403)
        return function(*args, **kwargs)
    return wrapper_function


# TODO: Use Werkzeug to hash the user's password when creating a new user.
@app.route('/register', methods = ["GET", "POST"])
def register():
    form = RegisterForm()
    if request.method == "POST" and form.validate_on_submit():
        enc_salt_pass = generate_password_hash(form.password.data, method= 'pbkdf2:sha256', salt_length = 8)
        new_user = User(
            name = form.name.data,
            email = form.email.data,
            password = enc_salt_pass,
        )
        result = db.session.execute(db.select(User).where(User.email==new_user.email))
        existing_mail = result.scalar()
        if existing_mail:
            flash('An account with this username already exists, please login.')
            return redirect(url_for('login'))
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('get_all_posts'))
    return render_template("register.html", form = form, current_user = current_user)


# TODO: Retrieve a user from the database based on their email. 
@app.route('/login',  methods= ["GET","POST"])
def login():
    form = LoginForm()
    if request.method == "POST" and form.validate_on_submit():
            email = form.email.data
            password = form.password.data
            result = db.session.execute(db.select(User).where(User.email == email))
            user = result.scalar()
            
            if not user:
                flash('A User With This Email Address Does Not Exist')
                return redirect(url_for('login'))
            elif not check_password_hash(user.password,password):
                flash('Invalid Password')
                return redirect(url_for('login'))
            else:
                login_user(user)
                return redirect(url_for('get_all_posts'))
    return render_template("login.html", form = form, current_user = current_user)
    


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route('/')
def get_all_posts():
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    return render_template("index.html", all_posts=posts, current_user=current_user)


# TODO: Allow logged-in users to comment on posts
@app.route("/post/<int:post_id>", methods = ["GET", "POST"])
def show_post(post_id):
    requested_post = db.get_or_404(BlogPost, post_id)
    comment_form = CommentForm()
    if comment_form.validate_on_submit():
        if not current_user.is_authenticated:
            flash('You need to login')
            return redirect(url_for('login'))
        
        new_comment = Comment(
            text = comment_form.comment.data,
            comment_author = current_user,
            parent_post = requested_post,
            )
        db.session.add(new_comment)
        db.session.commit()
    return render_template("post.html", post=requested_post, current_user = current_user, form = comment_form)


# TODO: Use a decorator so only an admin user can create a new post
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
    return render_template("make-post.html", form=form, current_user = current_user)


# TODO: Use a decorator so only an admin user can edit a post
@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
        
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True, current_user = current_user)


# TODO: Use a decorator so only an admin user can delete a post
@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/about")
def about():
    return render_template("about.html", current_user = current_user)


@app.route("/contact")
def contact():
    return render_template("contact.html", current_user = current_user)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
