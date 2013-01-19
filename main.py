#!/usr/local/bin/python
# -*- coding: utf-8 -*-

import os
import webapp2
import jinja2
import random
from models import *
from google.appengine.api import users
from google.appengine.ext import deferred


def dtf(value, format='%d-%m-%Y'):
    return value.strftime(format)

jinja_environment = jinja2.Environment(
    loader=jinja2.FileSystemLoader('templates'))
jinja_environment.filters['dtf'] = dtf


class BaseHandler(webapp2.RequestHandler):
    def generate(self, template_name, template_values={}):
        tornei = Tornei.query()
        if users.get_current_user():
            url = users.create_logout_url("/")
            login = 'Esci'
        else:
            url = users.create_login_url("/")
            login = 'Entra'
        values = {
            'url': url,
            'login': login,
            'tornei': tornei,
            'admin': users.is_current_user_admin(),
            'brand': "Tornei"
            }
        values.update(template_values)
        template = jinja_environment.get_template(template_name)
        self.response.write(template.render(values))


class MainPage(BaseHandler):
    def get(self):
        matchs = Match.query(Match.disputa == True)
        matchs = matchs.order(-Match.timestamp)
        matchs = matchs.fetch(10)
        self.generate('home.html', {'matchs': matchs})


class TorneoPage(BaseHandler):
    def get(self):
        torneo = Tornei.get_by_id(int(self.request.get('id')))
        self.generate('torneo.html', {'t': torneo})


class Classifica(BaseHandler):
    def get(self):
        torneo = Tornei.get_by_id(int(self.request.get('id')))
        self.generate('classifica.html', {'t': torneo})


class GiornataPage(BaseHandler):
    def get(self):
        giornata = Giornate.get_by_id(int(self.request.get('id')))
        pq = Giornate.query(Giornate.giornata == (giornata.giornata - 1))
        nq = Giornate.query(Giornate.giornata == (giornata.giornata + 1))
        if pq.get():
            prev = pq.get().key.id()
        else:
            prev = None
        if nq.get():
            next = nq.get().key.id()
        else:
            next = None
        values = {
        'g': giornata,
        'next': next,
        'prev': prev,
        't': giornata.torneo.get()
        }
        if users.is_current_user_admin():
            self.generate('g_edit.html', values)
        else:
            self.generate('g_view.html', values)


class EditTennisti(BaseHandler):
    def post(self):
        t = Tennisti.get_by_id(int(self.request.get('id')))
        t.squadra = self.request.get('squadra')
        t.nome = self.request.get('nome')
        t.telefono = self.request.get('telefono')
        t.email = self.request.get('email')
        t.put()
        self.redirect(self.request.referer)


class CheckPage(BaseHandler):
    def get(self):
        torneo = Tornei.get_by_id(int(self.request.get('id')))
        if users.is_current_user_admin():
            self.generate('ten_edit.html', {'t': torneo})
        else:
            self.generate('check.html', {'t': torneo})


class Checknum(BaseHandler):
    def post(self):
        torneo = Tornei.get_by_id(int(self.request.get('id')))
        telefono = self.request.get('telefono')
        q = Tennisti.query(Tennisti.torneo == torneo.key,
                           Tennisti.telefono == telefono)
        if q.get():
            self.generate('ten_view.html', {'t': torneo})
        else:
            self.redirect('/')


class AddRisultato(webapp2.RequestHandler):
    def post(self):
        incasa1 = self.request.get('incasa1')
        ospite1 = self.request.get('ospite1')
        incasa2 = self.request.get('incasa2')
        ospite2 = self.request.get('ospite2')
        a, b = Match.risultati(incasa1, ospite1, incasa2, ospite2)
        m = Match.get_by_id(int(self.request.get('id')))
        m.incasa1 = validate(incasa1)
        m.ospite1 = validate(ospite1)
        m.incasa2 = validate(incasa2)
        m.ospite2 = validate(ospite2)
        m.incasaP = 3 if a == 2 else a
        m.ospiteP = 3 if b == 2 else b
        m.put()
        self.redirect(self.request.referer)


class Admin(BaseHandler):
    def get(self):
        self.generate('admin.html', {})


class Creatorneo(BaseHandler):
    def post(self):
        torneo = Tornei()
        torneo.organiz = self.request.get('organiz')
        torneo.numero = int(self.request.get('numero'))
        torneo.nome = self.request.get('nome')
        torneo.anno = int(self.request.get('anno'))
        torneo.put()
        deferred.defer(popola_torneo, torneo.key, _queue='worker')
        self.redirect(self.request.referer)


def popola_torneo(t_key):
    torneo = t_key.get()
    lettere = ['a', 'b', 'c', 'de', 'f', 'g', 'h', 'i', 'l', 'm',
    'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'z']
    _squadre = ['roma', 'juve', 'lazio', 'milan', 'inter', 'samp',
    'genoa', 'catania', 'bari', 'atalanta', 'andria', 'barletta', 'chievo',
    'pescara', 'fiorentina', 'palermo', 'napoli', 'siena', 'udine', 'bologna']
    n = 0
    while n < 20:
        ten = Tennisti()
        ten.nome = ''.join(random.sample(lettere, 5))
        ten.squadra = _squadre[n]
        ten.torneo = torneo.key
        ten.put()
        n += 1
    tqry = Tennisti.query(Tennisti.torneo == torneo.key)

    tennisti = [t.key for t in tqry]
    if not len(tennisti) % 2 == 0:
        ten = Tennisti(squadra='riposo',
                       torneo=torneo.key)
        ten.put()
        tennisti.append(ten.key)
    deferred.defer(Berger, tennisti, torneo.key, 0, _queue='worker')
    deferred.defer(Berger, tennisti, torneo.key, 1, _queue='worker')


def Berger(tennisti, torneo_key, turno):
    _turno = 'andata' if turno == 0 else 'ritorno'

    i = 0
    while i < len(tennisti) - 1:
        gr = Giornate(giornata=i + 1,
                      torneo=torneo_key,
                      turno=_turno)
        gr.put()

        j = 0
        while j < (len(tennisti) / 2):
            if i % 2 != turno:
                deferred.defer(crea_match,
                               torneo_key,
                               gr.key,
                               tennisti[j],
                               tennisti[len(tennisti) - 1 - j],
                               _queue='worker')
            else:
                deferred.defer(crea_match,
                               torneo_key,
                               gr.key,
                               tennisti[len(tennisti) - 1 - j],
                               tennisti[j],
                               _queue='worker')
            j += 1
        tennisti.insert(1, tennisti.pop())
        i += 1


def crea_match(torneo_key, g_key, t1_key, t2_key):
    match = Match(torneo=torneo_key,
                  giornata=g_key,
                  incasa=t1_key,
                  ospite=t2_key
                  )
    match.put()


def validate(x):
    try:
        int(x)
    except:
        return int(0)
    return int(x)


debug = os.environ.get('SERVER_SOFTWARE', '').startswith('Dev')
app = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/c', Classifica),
    ('/t', TorneoPage),
    ('/g', GiornataPage),
    ('/k', CheckPage),
    ('/checknum', Checknum),
    ('/add', AddRisultato),
    ('/edit_t', EditTennisti),
    ('/admin', Admin),
    ('/admin/creatorneo', Creatorneo),
    ], debug=debug)


def main():
    app.run()


if __name__ == "__main__":
    main()
