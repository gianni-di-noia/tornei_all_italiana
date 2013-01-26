#!/usr/local/bin/python
# -*- coding: utf-8 -*-

import os
import jinja2
import webapp2
from google.appengine.api import users

config = {
'domain': 'tornei.dinoia.eu',
'path': 'http://tornei.dinoia.eu/bacheca',
'title': "Tornei",
'editor': "Circolo Tennis Au Coq d'Or",
'email': 'info@circoloitalia.tk',
}

debug = os.environ.get('SERVER_SOFTWARE', '').startswith('Dev')


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


class BaseHandler(webapp2.RequestHandler):
    def generate(self, template_name, template_values={}):
        if users.get_current_user():
            url = users.create_logout_url("/")
            login = 'Esci'
        else:
            url = users.create_login_url("/")
            login = 'Entra'
        values = {
            'url': url,
            'login': login,
            'admin': users.is_current_user_admin(),
            'config': config
            }
        values.update(template_values)
        template = jinja_environment.get_template(template_name)
        self.response.write(template.render(values))
