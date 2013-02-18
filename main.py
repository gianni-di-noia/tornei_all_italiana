#!/usr/local/bin/python
# -*- coding: utf-8 -*-

import base
from models import *
from google.appengine.api import users, mail
from google.appengine.ext import deferred


class MainPage(base.BaseHandler):
    def get(self):
        tornei = Tornei.query()
        matchs = Match.query(Match.disputa == True).order(-Match.timestamp).fetch(10)
        posts = Post.query(Post.published == True).order(-Post.create).fetch(10)
        self.generate('home.html', {'matchs': matchs, 'posts': posts, 'tornei': tornei})


class TorneoPage(base.BaseHandler):
    def get(self):
        torneo = Tornei.get_by_id(int(self.request.get('id')))
        self.response.set_cookie('torneo', str(torneo.id), max_age=360)
        self.generate('torneo.html', {'t': torneo})


class Classifica(base.BaseHandler):
    def get(self):
        torneo = Tornei.get_by_id(int(self.request.get('id')))
        self.response.set_cookie('torneo', str(torneo.id), max_age=360)
        self.generate('classifica.html', {'t': torneo})


class GiornataPage(base.BaseHandler):
    def get(self):
        giornata = Giornate.get_by_id(int(self.request.get('id')))
        pq = Giornate.query(Giornate.giornata == (giornata.giornata - 1))
        nq = Giornate.query(Giornate.giornata == (giornata.giornata + 1))
        prev = pq.get().key.id() if pq.get() else None
        next = nq.get().key.id() if nq.get() else None
        values = {'g': giornata, 'next': next, 'prev': prev, 't': giornata.torneo.get()}
        if users.is_current_user_admin():
            self.generate('g_edit.html', values)
        else:
            self.generate('g_view.html', values)


class EditTennisti(base.BaseHandler):
    def post(self):
        t = Tennisti.get_by_id(int(self.request.get('id')))
        t.squadra = self.request.get('squadra')
        t.nome = self.request.get('nome')
        t.telefono = self.request.get('telefono')
        t.email = self.request.get('email')
        t.put()
        self.redirect(self.request.referer)


class CheckPage(base.BaseHandler):
    def get(self):
        torneo = Tornei.get_by_id(int(self.request.get('id')))
        self.response.set_cookie('torneo', str(torneo.id), max_age=360)
        self.generate('check.html', {'t': torneo})

    def post(self):
        torneo = Tornei.get_by_id(int(self.request.get('id')))
        telefono = self.request.get('telefono')
        if torneo.check(telefono):
            self.response.set_cookie('telefono', str(telefono), max_age=360)
        self.redirect('/')


class TennistiPage(base.BaseHandler):
    def get(self):
        torneo = Tornei.get_by_id(int(self.request.get('id')))
        self.response.set_cookie('torneo', str(torneo.id), max_age=360)
        if users.is_current_user_admin():
            self.generate('ten_edit.html', {'t': torneo})
        elif self.tu:
            self.generate('ten_view.html', {'t': torneo})
        else:
            self.redirect('/k?id=' + str(torneo.key.id()))


class PersonalePage(base.BaseHandler):
    def get(self):
        torneo = Tornei.get_by_id(int(self.request.get('id')))
        self.response.set_cookie('torneo', str(torneo.id), max_age=360)
        if self.tu:
            self.generate('personale.html', {'tu': self.tu, 't': torneo})
        else:
            self.redirect('/k?id=' + str(torneo.key.id()))


class Invita(base.BaseHandler):
    def get(self):
        avv = Tennisti.get_by_id(int(self.request.get('id')))
        self.generate('invita.html', {'tu': self.tu, 'avv': avv, 'torneo': self.torneo})

    def post(self):
        avv = Tennisti.get_by_id(int(self.request.get('id')))
        subject = "[Torneo di tennis] %s vuole disputare il match" % self.tu.nome
        body = self.request.get('comment')
        mail.send_mail(sender='info@circoloitalia.tk',
                       to=[str(avv.email), str(self.tu.email)],
                       subject=subject,
                       reply_to=self.tu.email,
                       body=body)
        self.redirect('/tu?id=' + str(self.torneo.id))


class AddRisultato(base.BaseHandler):
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


class Creatorneo(base.BaseHandler):
    def post(self):
        torneo_key = Tornei(organiz=self.request.get('organiz'),
                            numero=int(self.request.get('numero')),
                            nome=self.request.get('nome'),
                            anno=int(self.request.get('anno'))).put()
        deferred.defer(popola_torneo, torneo_key, _queue='worker')
        self.redirect(self.request.referer)


def popola_torneo(torneo_key):
    _squadre = ['roma', 'juve', 'lazio', 'milan', 'inter', 'samp', 'genoa', 'catania', 'bari',
    'atalanta', 'andria', 'barletta', 'chievo', 'pescara', 'fiorentina', 'palermo', 'napoli',
    'siena', 'udine', 'bologna']
    n = 0
    while n < 20:
        Tennisti(squadra=_squadre[n], torneo=torneo_key).put()
        n += 1

    tennisti = Tennisti.query(Tennisti.torneo == torneo_key).fetch(keys_only=True)

    if not len(tennisti) % 2 == 0:
        ten_key = Tennisti(squadra='riposo', torneo=torneo_key).put()
        tennisti.append(ten_key)
    deferred.defer(Berger, tennisti, torneo_key, 0, _queue='worker')
    deferred.defer(Berger, tennisti, torneo_key, 1, _queue='worker')


def Berger(tennisti, torneo_key, turno):
    _turno = 'andata' if turno == 0 else 'ritorno'

    i = 0
    while i < len(tennisti) - 1:
        gr_key = Giornate(giornata=i + 1, torneo=torneo_key, turno=_turno).put()

        j = 0
        while j < (len(tennisti) / 2):
            if i % 2 != turno:
                deferred.defer(crea_match,
                               torneo_key,
                               gr_key,
                               tennisti[j],
                               tennisti[len(tennisti) - 1 - j],
                               _queue='worker')
            else:
                deferred.defer(crea_match,
                               torneo_key,
                               gr_key,
                               tennisti[len(tennisti) - 1 - j],
                               tennisti[j],
                               _queue='worker')
            j += 1
        tennisti.insert(1, tennisti.pop())
        i += 1


def crea_match(torneo_key, g_key, t1_key, t2_key):
    Match(torneo=torneo_key, giornata=g_key, incasa=t1_key, ospite=t2_key).put()


def validate(x):
    try:
        int(x)
    except:
        return int(0)
    return int(x)


import webapp2
app = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/c', Classifica),
    ('/t', TorneoPage),
    ('/g', GiornataPage),
    ('/k', CheckPage),
    ('/tennisti', TennistiPage),
    ('/invita', Invita),
    ('/tu', PersonalePage),
    ('/add', AddRisultato),
    ('/edit_t', EditTennisti),
    ('/admin/creatorneo', Creatorneo),
], debug=base.debug)


if __name__ == "__main__":
    app.run()
