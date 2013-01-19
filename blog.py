#!/usr/local/bin/python
# -*- coding: utf-8 -*-

import os
import jinja2
import webapp2
from webapp2_extras import routes
from google.appengine.api import users, images, memcache
from google.appengine.ext import ndb, blobstore
from google.appengine.ext.webapp import blobstore_handlers

config = {
'domain': 'www.example.org',
'path': 'http://www.example.org/blog',
'title': "Tornei",
'editor': 'name surname',
'email': 'admin@example.org',
}


def dtf(value, format='%d/%m/%Y %H:%M'):
    return value.strftime(format)


def dtfeed(value):
    return value.isoformat() + 'Z'


def dtitem(value, format='%Y-%m-%d'):
    return value.strftime(format)

jinja_environment = jinja2.Environment(
    loader=jinja2.FileSystemLoader('templates'))
jinja_environment.filters['dtf'] = dtf
jinja_environment.filters['dtfeed'] = dtfeed
jinja_environment.filters['dtitem'] = dtitem


class Tag(ndb.Model):
    name = ndb.StringProperty()

    @property
    def id(self):
        return self.key.id()

    @classmethod
    def tags_pub(self):
        post_pub = Post.query(Post.published == True)
        tags = []
        for post in post_pub:
            for tag in post.tags:
                if tag not in tags:
                    tags.append(tag)
        return [tag.get() for tag in tags]


class Post(ndb.Model):
    tags = ndb.KeyProperty(kind=Tag, repeated=True)
    title = ndb.StringProperty()
    href = ndb.StringProperty()
    content = ndb.TextProperty()
    create = ndb.DateTimeProperty(auto_now_add=True)
    update = ndb.DateTimeProperty(auto_now=True)
    published = ndb.BooleanProperty(default=False)

    @property
    def comments(self):
        return Comment.query(Comment.post == self.key).order(Comment.create)

    @property
    def id(self):
        return self.key.id()


class Comment(ndb.Model):
    post = ndb.KeyProperty(kind=Post)
    name = ndb.StringProperty(required=True)
    url = ndb.StringProperty()
    create = ndb.DateTimeProperty(auto_now_add=True)
    published = ndb.BooleanProperty(default=True)
    comment = ndb.TextProperty(required=True)

    @property
    def id(self):
        return self.key.id()


class BaseHandler(webapp2.RequestHandler):
    def generate(self, template_name, template_values={}):
        if users.is_current_user_admin():
            url = users.create_logout_url("/")
            linktext = 'Logout'
        else:
            url = users.create_login_url(self.request.uri)
            linktext = 'Login'
        values = {
            'url': url,
            'linktext': linktext,
            'admin': users.is_current_user_admin(),
            'config': config
            }
        values.update(template_values)
        template = jinja_environment.get_template(template_name)
        self.response.write(template.render(values))


class FeedHandler(webapp2.RequestHandler):
    def get(self):
        posts = Post.query(Post.published == True).order(-Post.create)
        values = {
        'posts': posts.fetch(10),
        'update': posts.get().create,
        'config': config
        }
        template = jinja_environment.get_template('blog/atom.xml')
        self.response.headers['Content-Type'] = 'application/xml'
        self.response.write(template.render(values))


class HomePage(BaseHandler):
    def get(self):
        cursor = self.request.get('c')
        c = ndb.Cursor(urlsafe=cursor)
        qry = Post.query(Post.published == True).order(-Post.create)
        posts, next_curs, more = qry.fetch_page(10, start_cursor=c)
        if more and next_curs:
            next_c = next_curs.urlsafe()
        else:
            next_c = None
        values = {'posts': posts, 'c': next_c}
        self.generate('blog/posts.html', values)


class DraftsPage(BaseHandler):
    def get(self):
        cursor = self.request.get('c')
        c = ndb.Cursor(urlsafe=cursor)
        qry = Post.query(Post.published == False).order(-Post.create)
        posts, next_curs, more = qry.fetch_page(10, start_cursor=c)
        if more and next_curs:
            next_c = next_curs.urlsafe()
        else:
            next_c = None
        values = {'posts': posts, 'c': next_c}
        self.generate('blog/posts.html', values)


class PostPage(BaseHandler):
    def get(self, post):
        p = Post.get_by_id(int(post))
        if users.is_current_user_admin() or p.published:
            self.generate('blog/post.html', {'p': p})
        else:
            self.redirect('/')


class TagsPage(BaseHandler):
    def get(self):
        if users.is_current_user_admin():
            tags = Tag.query().order(-Tag.name)
        else:
            tags = Tag.tags_pub()
        self.generate('blog/tagcloud.html', {'tags': tags})


class TagPage(BaseHandler):
    def get(self, tag):
        cursor = self.request.get('c')
        c = ndb.Cursor(urlsafe=cursor)
        t = Tag.get_by_id(tag)
        qry = Post.query(Post.published == True)
        qry = qry.filter(Post.tags == t.key).order(-Post.create)
        posts, next_curs, more = qry.fetch_page(10, start_cursor=c)
        if more and next_curs:
            next_c = next_curs.urlsafe()
        else:
            next_c = None
        values = {'posts': posts, 'c': next_c}
        self.generate('blog/posts.html', values)


class NewPost(webapp2.RequestHandler):
    def get(self):
        p = Post()
        p.title = 'title'
        p.content = 'content'
        p.put()
        self.redirect('/blog/admin/edit/%s' % p.id)


class SubmitPost(webapp2.RequestHandler):
    def get(self):
        content = self.request.get('content').encode('utf8')
        p = Post()
        p.title = self.request.get('title')
        p.href = self.request.get('href')
        p.content = """<blockquote><p>%s</p></blockquote> """ % content
        p.put()
        self.redirect('/blog/admin/edit/%s' % p.id)


class EditPost(BaseHandler):
    def get(self, post):
        p = Post.get_by_id(int(post))
        values = {
        'tags': Tag.query(),
        'p': p,
        'upload_url': blobstore.create_upload_url('/upload'),
        'code': memcache.get('last_img')
        }
        self.generate('blog/edit.html', values)

    def post(self, post):
        p = Post.get_by_id(int(post))
        p.title = self.request.get('title')
        p.href = self.request.get('href')
        p.content = self.request.get('content')
        p.put()
        self.redirect(self.request.referer)


class AddComment(webapp2.RequestHandler):
    def post(self, post):
        p = Post.get_by_id(int(post))
        c = Comment()
        c.post = p.key
        c.name = self.request.get('name')
        c.url = self.request.get('url')
        c.comment = self.request.get('comment')
        c.put()
        self.redirect('/blog/post/%s' % p.id)


class PublishPost(webapp2.RequestHandler):
    def get(self, post):
        p = Post.get_by_id(int(post))
        if p.published == False:
            import datetime
            p.create = datetime.datetime.now()
            p.published = True
        else:
            p.published = False
        p.put()
        self.redirect('/blog/post/%s' % p.id)


class DeletePost(webapp2.RequestHandler):
    def get(self, post):
        p = Post.get_by_id(int(post))
        p.key.delete()
        self.redirect('/blog/admin/drafts')


class NewTag(webapp2.RequestHandler):
    def post(self, post):
        name = self.request.get('tag')
        tag = Tag.get_or_insert(name, name=name)
        p = Post.get_by_id(int(post))
        p.tags.append(tag.key)
        p.put()
        self.redirect(self.request.referer)


class Assign(webapp2.RequestHandler):
    def get(self, post, tag):
        p = Post.get_by_id(int(post))
        t = Tag.get_by_id(tag)
        if t.key in p.tags:
            p.tags.remove(t.key)
        else:
            p.tags.append(t.key)
        p.put()
        self.redirect(self.request.referer)


class UploadHandler(blobstore_handlers.BlobstoreUploadHandler):
    def post(self):
        upload_files = self.get_uploads('file')
        blob_info = upload_files[0]
        img_url = images.get_serving_url(blob_info.key(), size=767, crop=False)
        string = '<img src="%s" class="img-polaroid">' % img_url
        memcache.set('last_img', string)
        self.redirect(self.request.referer)


class script(webapp2.RequestHandler):
    """docstring for script"""
    def get(self):
        posts = Post.query()
        for p in posts:
            p.published = False
            p.put()

debug = os.environ.get('SERVER_SOFTWARE', '').startswith('Dev')

app = webapp2.WSGIApplication([
    routes.RedirectRoute('/blog/', HomePage, name='Blog', strict_slash=True),
    routes.PathPrefixRoute('/blog', [
        webapp2.Route('/atom', FeedHandler),
        webapp2.Route(r'/post/<post:(.*)>', PostPage),
        webapp2.Route('/tags/', TagsPage),
        webapp2.Route(r'/tag/<tag:(.*)>', TagPage),
        webapp2.Route(r'/comment/<post:(.*)>', AddComment),
        webapp2.Route('/admin/new', NewPost),
        webapp2.Route('/admin/submit', SubmitPost),
        webapp2.Route('/admin/upload', UploadHandler),
        webapp2.Route('/admin/script', script),
        webapp2.Route('/admin/drafts', DraftsPage),
        webapp2.Route(r'/admin/edit/<post:(.*)>', EditPost),
        webapp2.Route(r'/admin/publish/<post:(.*)>', PublishPost),
        webapp2.Route(r'/admin/delete/<post:(.*)>', DeletePost),
        webapp2.Route(r'/admin/newtag/<post:(.*)>', NewTag),
        webapp2.Route(r'/admin/assign/<post:(.*)>/<tag:(.*)>', Assign),
    ]), ], debug=debug)


def blog():
    app.run()

if __name__ == "__main__":
    blog()
