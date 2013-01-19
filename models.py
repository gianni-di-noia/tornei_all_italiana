#!/usr/local/bin/python
# -*- coding: utf-8 -*-

from google.appengine.ext import ndb


class Tornei(ndb.Expando):
    nome = ndb.StringProperty()
    organiz = ndb.StringProperty()
    numero = ndb.IntegerProperty()
    anno = ndb.IntegerProperty()
    match_tot = ndb.IntegerProperty()

    def disputate(self):
        return Match.query(Match.torneo == self.key,
                           Match.disputa == True).count()

    @property
    def tennisti_set(self):
        qry = Tennisti.query(Tennisti.torneo == self.key)
        return qry.order(-Tennisti.punti)

    @property
    def match_set(self):
        return Match.query(Match.torneo == self.key)

    @property
    def andata(self):
        q = Giornate.query(Giornate.torneo == self.key)
        q = q.filter(Giornate.turno == 'andata')
        q = q.order(Giornate.giornata)
        return q

    @property
    def ritorno(self):
        q = Giornate.query(Giornate.torneo == self.key)
        q = q.filter(Giornate.turno == 'ritorno')
        q = q.order(Giornate.giornata)
        return q

    @property
    def id(self):
        return self.key.id()


class Tennisti(ndb.Expando):
    nome = ndb.StringProperty(indexed=False)
    telefono = ndb.StringProperty()
    email = ndb.StringProperty(indexed=False)
    squadra = ndb.StringProperty(indexed=False)
    data = ndb.DateTimeProperty(auto_now=True)
    torneo = ndb.KeyProperty(kind=Tornei)
    puntiincasa = ndb.IntegerProperty(default=0)
    puntiospite = ndb.IntegerProperty(default=0)
    punti = ndb.ComputedProperty(lambda self: self.puntiincasa + self.puntiospite)
    disputati = ndb.IntegerProperty(default=0)
    vinti = ndb.IntegerProperty(default=0)
    pareggiati = ndb.IntegerProperty(default=0)

    @property
    def persi(self):
        return self.disputati - self.vinti - self.pareggiati

    @staticmethod
    def calc_disputati(tennista):
        q = Match.query(Match.torneo == tennista.torneo)
        q1 = q.filter(Match.ospite == tennista.key, Match.disputa == True)
        q2 = q.filter(Match.incasa == tennista.key, Match.disputa == True)
        return q1.count() + q2.count()

    @staticmethod
    def calc_vinti(tennista):
        q = Match.query(Match.torneo == tennista.torneo)
        q1 = q.filter(Match.incasaP == 3, Match.incasa == tennista.key)
        q2 = q.filter(Match.ospiteP == 3, Match.ospite == tennista.key)
        return q1.count() + q2.count()

    @staticmethod
    def calc_pareggiati(tennista):
        q = Match.query(Match.torneo == tennista.torneo)
        q1 = q.filter(Match.incasaP == 1, Match.incasa == tennista.key)
        q2 = q.filter(Match.ospiteP == 1, Match.ospite == tennista.key)
        return q1.count() + q2.count()


class Giornate(ndb.Expando):
    giornata = ndb.IntegerProperty()
    data = ndb.DateTimeProperty()
    torneo = ndb.KeyProperty(kind=Tornei)
    turno = ndb.StringProperty(choices=['andata', 'ritorno'])

    @property
    def match_set(self):
        return Match.query(Match.giornata == self.key)

    @property
    def disputate(self):
        return Match.query(Match.giornata == self.key, Match.disputa == True).count()


class Match(ndb.Expando):
    timestamp = ndb.DateTimeProperty(auto_now=True)
    torneo = ndb.KeyProperty(kind=Tornei)
    giornata = ndb.KeyProperty(kind=Giornate)
    incasa = ndb.KeyProperty(kind=Tennisti)
    ospite = ndb.KeyProperty(kind=Tennisti)
    disputa = ndb.ComputedProperty(lambda self: True if sum([self.incasa1, self.ospite1]) > 0 else False)

    incasa1 = ndb.IntegerProperty(default=0)
    ospite1 = ndb.IntegerProperty(default=0)
    incasa2 = ndb.IntegerProperty(default=0)
    ospite2 = ndb.IntegerProperty(default=0)
    incasaP = ndb.IntegerProperty(default=0)
    ospiteP = ndb.IntegerProperty(default=0)

    def _post_put_hook(self, future):
        self.inserisci_punteggi(self.incasa)
        self.inserisci_punteggi(self.ospite)

    @staticmethod
    def inserisci_punteggi(t_k):
        n_incasa = Match.query(Match.incasa == t_k)
        n_ospite = Match.query(Match.ospite == t_k)

        r_incasa = [n.incasaP for n in n_incasa]
        r_ospite = [n.ospiteP for n in n_ospite]

        t = t_k.get()
        t.puntiincasa = sum(r_incasa)
        t.puntiospite = sum(r_ospite)
        t.disputati = Tennisti.calc_disputati(t)
        t.vinti = Tennisti.calc_vinti(t)
        t.pareggiati = Tennisti.calc_pareggiati(t)
        t.put()

    @staticmethod
    def risultati(incasa1, ospite1, incasa2, ospite2):
        if incasa1 > ospite1:
            w1 = [1, 0]
        elif incasa1 < ospite1:
            w1 = [0, 1]
        else:
            w1 = [0, 0]

        if incasa2 > ospite2:
            w2 = [1, 0]
        elif incasa2 < ospite2:
            w2 = [0, 1]
        else:
            w2 = [0, 0]

        incasa = w1[0] + w2[0]
        ospite = w1[1] + w2[1]
        return [incasa, ospite]
