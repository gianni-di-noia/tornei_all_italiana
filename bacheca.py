#!/usr/local/bin/python
# -*- coding: utf-8 -*-

import base
from models import Post, Comment
from google.appengine.api import users, images, memcache
from google.appengine.ext import ndb, blobstore
from google.appengine.ext.webapp import blobstore_handlers


class FeedHandler(base.BaseHandler):
    def get(self):
        posts = Post.query(Post.published == True).order(-Post.create)
        values = {
        'posts': posts.fetch(10),
        'update': posts.get().create,
        }
        template = base.jinja_environment.get_template('bacheca/atom.xml')
        self.response.headers['Content-Type'] = 'application/xml'
        self.response.write(template.render(values))


class HomePage(base.BaseHandler):
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
        self.generate('bacheca/posts.html', values)


class DraftsPage(base.BaseHandler):
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
        self.generate('bacheca/posts.html', values)


class PostPage(base.BaseHandler):
    def get(self, post):
        p = Post.get_by_id(int(post))
        if users.is_current_user_admin() or p.published:
            self.generate('bacheca/post.html', {'p': p})
        else:
            self.redirect('/')


class NewPost(base.BaseHandler):
    def get(self):
        p = Post()
        p.title = 'title'
        p.content = 'content'
        p.put()
        self.redirect('/bacheca/admin/edit/%s' % p.id)


class EditPost(base.BaseHandler):
    def get(self, post):
        p = Post.get_by_id(int(post))
        values = {
        'p': p,
        'upload_url': blobstore.create_upload_url('/bacheca/admin/upload'),
        'code': memcache.get('last_img')
        }
        self.generate('bacheca/edit.html', values)

    def post(self, post):
        p = Post.get_by_id(int(post))
        p.title = self.request.get('title')
        p.content = self.request.get('content')
        p.put()
        self.redirect(self.request.referer)


class AddComment(base.BaseHandler):
    def post(self, post):
        p = Post.get_by_id(int(post))
        c = Comment(post=p.key,
                    name=self.request.get('name'),
                    comment=self.request.get('comment'))
        c.put()
        self.redirect('/bacheca/post/%s' % p.id)


class PublishPost(base.BaseHandler):
    def get(self, post):
        p = Post.get_by_id(int(post))
        if p.published == False:
            import datetime
            p.create = datetime.datetime.now()
            p.published = True
        else:
            p.published = False
        p.put()
        self.redirect('/bacheca/post/%s' % p.id)


class DeletePost(base.BaseHandler):
    def get(self, post):
        p = Post.get_by_id(int(post))
        p.key.delete()
        self.redirect('/bacheca/admin/')


class UploadHandler(blobstore_handlers.BlobstoreUploadHandler):
    def post(self):
        upload_files = self.get_uploads('file')
        blob_info = upload_files[0]
        img_url = images.get_serving_url(blob_info.key(), size=767, crop=False)
        string = '<img src="%s" class="img-polaroid">' % img_url
        memcache.set('last_img', string)
        self.redirect(self.request.referer)


import webapp2
from webapp2_extras import routes
app = webapp2.WSGIApplication([
    routes.RedirectRoute('/bacheca/', HomePage, name='Bacheca', strict_slash=True),
    routes.RedirectRoute('/bacheca/admin/', DraftsPage, name='Admin', strict_slash=True),
    routes.PathPrefixRoute('/bacheca', [
        webapp2.Route('/atom', FeedHandler),
        webapp2.Route(r'/post/<post:(.*)>', PostPage),
        webapp2.Route(r'/comment/<post:(.*)>', AddComment),
        webapp2.Route('/admin/new', NewPost),
        webapp2.Route('/admin/upload', UploadHandler),
        webapp2.Route(r'/admin/edit/<post:(.*)>', EditPost),
        webapp2.Route(r'/admin/publish/<post:(.*)>', PublishPost),
        webapp2.Route(r'/admin/delete/<post:(.*)>', DeletePost),
    ]), ], debug=base.debug)


def bacheca():
    app.run()

if __name__ == "__main__":
    bacheca()
