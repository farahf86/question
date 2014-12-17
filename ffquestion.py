# [START imports]
import os
import urllib
import datetime
import time

from google.appengine.api import users
from google.appengine.ext import ndb
from google.appengine.ext.ndb import msgprop
from google.appengine.ext import blobstore  
from google.appengine.ext.webapp import blobstore_handlers


import jinja2
import webapp2


JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)
# [END imports]

class Vote(ndb.Model):
    direction = ndb.IntegerProperty()
    user = ndb.UserProperty()

class Answer(ndb.Model):
    id = ndb.StringProperty()
    user = ndb.UserProperty()
    creationDate = ndb.DateTimeProperty(auto_now_add=True)
    lastUpdateDate = ndb.DateTimeProperty(auto_now=True)
    name = ndb.StringProperty()
    description = ndb.TextProperty()
    votes = ndb.StructuredProperty(Vote, repeated=True)
    images = ndb.BlobKeyProperty(repeated=True)
    _use_memcache = False
    _use_cache = False

class Question(ndb.Model):
    id = ndb.StringProperty()
    user = ndb.UserProperty()
    creationDate = ndb.DateTimeProperty(auto_now_add=True)
    lastUpdateDate = ndb.DateTimeProperty(auto_now=True)
    name = ndb.StringProperty()
    description = ndb.TextProperty()
    answers = ndb.LocalStructuredProperty(Answer, repeated=True)
    votes = ndb.StructuredProperty(Vote, repeated=True)
    tags = ndb.StringProperty(repeated=True)
    images = ndb.BlobKeyProperty(repeated=True)
    _use_memcache = False
    _use_cache = False

# [START main_page]
class MainPage(webapp2.RequestHandler):

    def get(self):

        user = users.get_current_user()
        nickname = ""

        if user:
            url = users.create_logout_url(self.request.uri)
            nickname = user.nickname()
        else:
            url = users.create_login_url(self.request.uri)

        questions_query = Question.query().order(-Question.lastUpdateDate)

        cursor = ndb.Cursor(urlsafe=self.request.get('cursor'))
        questions, next_curs, more = questions_query.fetch_page(10, start_cursor=cursor) 
        if more:
            next_c = next_curs.urlsafe()
        else:
            next_c = None

        for question in questions:
            
            canVoteUp = True
            canVoteDown = True
            totalVotes = 0

            for vote in question.votes:
                totalVotes += vote.direction

                if vote.user == user and vote.direction == 1:
                    canVoteUp = False

                if vote.user == user and vote.direction == -1:
                    canVoteDown = False

            question.totalVotes = totalVotes
            question.canVoteDown = canVoteDown
            question.canVoteUp = canVoteUp

        template_values = {
            'user' : user,
            'nickname' : nickname,
            'questions': questions,
            'url': url,
            'cursor': next_c
        }

        template = JINJA_ENVIRONMENT.get_template('index.html')
        self.response.write(template.render(template_values))
# [END main_page]

class PrepareQuestion(webapp2.RequestHandler):

    def get(self):
        
        user = users.get_current_user()
        nickname = ""

        if user:
            url = users.create_logout_url(self.request.uri)
            nickname = user.nickname()
        else:
            url = users.create_login_url(self.request.uri)

        

        template_values = {
            'user' : user,
            'nickname' : nickname,
            'url': url,
        }

        template = JINJA_ENVIRONMENT.get_template('addquestion.html')
        self.response.write(template.render(template_values))

class CreateQuestion(webapp2.RequestHandler):

    def post(self):
        question = Question()

        if users.get_current_user():
            question.user = users.get_current_user()

        question.id = str(time.time())
        question.name = self.request.get('title')
        question.description = self.request.get('description')
        question.tags = self.request.get_all('tags')

        question.put()

        self.redirect('/');

class ViewQuestion(webapp2.RequestHandler):

    def get(self):

        user = users.get_current_user()
        nickname = ""

        if user:
            url = users.create_logout_url(self.request.uri)
            nickname = user.nickname()
        else:
            url = users.create_login_url(self.request.uri)

        question_query = Question.query(Question.id == self.request.get('id'))

        question = question_query.fetch()[0]

        creator = True
        if question.user != user:
            creator = False

        for answer in question.answers:
            canVoteUp = True
            canVoteDown = True
            totalUpVotes = 0
            totalDownVotes = 0
            totalVotes = 0

            answercreator = True

            if answer.user != user:
                answercreator = False

            for vote in answer.votes:

                totalVotes += vote.direction

                if vote.direction == 1:
                    totalUpVotes+=1

                    if vote.user == user:
                        canVoteUp = False

                else:
                    totalDownVotes-=1

                    if vote.user == user:
                        canVoteDown = False

            answer.creator = answercreator
            answer.difference = totalUpVotes - totalDownVotes
            answer.canVoteDown = canVoteDown
            answer.canVoteUp = canVoteUp
            answer.totalVotes = totalVotes

        question.answers.sort(key=lambda x: x.difference)

        upload_url = blobstore.create_upload_url('/upload')

        template_values = {
            'user' : user,
            'nickname' : nickname,
            'question': question,
            'url': url,
            'creator': creator,
            'upload_url': upload_url
        }

        template = JINJA_ENVIRONMENT.get_template('viewquestion.html')
        self.response.write(template.render(template_values))

class CreateAnswer(webapp2.RequestHandler):

    def post(self):

        upload_url = blobstore.create_upload_url('/upload')

        question_query = Question.query(Question.id == self.request.get('qid'))
        question = question_query.fetch()[0]

        answer = Answer()

        if users.get_current_user():
            answer.user = users.get_current_user()

        currentTime = str(time.time())
        answer.id = currentTime
        answer.name = self.request.get('title')
        answer.description = self.request.get('description')

        answer.put()
        question.answers.append(answer)
        question.put()

        template_values = {
            'answer': answer,
            'qid' : self.request.get('qid'),
            'upload_url': upload_url
        }

        template = JINJA_ENVIRONMENT.get_template('viewanswer.html')
        self.response.write(template.render(template_values))

class EditQuestion(webapp2.RequestHandler):

    def post(self):

        question_query = Question.query(Question.id == self.request.get('id'))
        question = question_query.fetch()[0]

        question.name = self.request.get('title')
        question.description = self.request.get('description')
        question.tags = self.request.get_all('tags')

        question.put()

class QuestionVote(webapp2.RequestHandler):

    def post(self):

        question_query = Question.query(Question.id == self.request.get('id'))
        question = question_query.fetch()[0]

        vote = Vote()

        if users.get_current_user():
            vote.user = users.get_current_user()

        vote.direction = int(self.request.get('direction'))

        vote.put()
        question.votes.append(vote)
        question.put()

class AnswerVote(webapp2.RequestHandler):

    def post(self):

        question_query = Question.query(Question.id == self.request.get('qid'))
        question = question_query.fetch()[0]

        vote = Vote()

        if users.get_current_user():
            vote.user = users.get_current_user()

        vote.direction = int(self.request.get('direction'))

        vote.put()

        for answer in question.answers:
            if answer.id == self.request.get('id'):
                answer.votes.append(vote)

        question.put()

class Search(webapp2.RequestHandler):

    def post(self):

        user = users.get_current_user()

        if self.request.get('tag') != "":
            question_query = Question.query(Question.tags == self.request.get('tag'))
        else:
            question_query = Question.query().order(-Question.lastUpdateDate)

        questions = question_query.fetch(10)

        for question in questions:
            
            canVoteUp = True
            canVoteDown = True
            totalVotes = 0

            for vote in question.votes:
                totalVotes += vote.direction

                if vote.user == user and vote.direction == 1:
                    canVoteUp = False

                if vote.user == user and vote.direction == -1:
                    canVoteDown = False

            question.totalVotes = totalVotes
            question.canVoteDown = canVoteDown
            question.canVoteUp = canVoteUp

        template_values = {
            'questions': questions,
        }

        template = JINJA_ENVIRONMENT.get_template('questions.html')
        self.response.write(template.render(template_values))


class UploadHandler(blobstore_handlers.BlobstoreUploadHandler):

  def post(self):

    upload_files = self.get_uploads('file')  # 'file' is file upload field in the form
    blob_info = upload_files[0]

    question_query = Question.query(Question.id == self.request.get('qid'))
    question = question_query.fetch()[0]

    if self.request.get('aid') != "":
        for answer in question.answers:
            if answer.id == self.request.get('aid'):
                answer.images.append(blob_info.key())
    else:
        question.images.append(blob_info.key())
    

    question.put()

    self.redirect('/viewquestion?id=%s' % self.request.get('qid'))

class ServeHandler(blobstore_handlers.BlobstoreDownloadHandler):

  def get(self, resource):
    
    resource = str(urllib.unquote(resource))
    blob_info = blobstore.BlobInfo.get(resource)
    self.send_blob(blob_info)

application = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/preparequestion', PrepareQuestion),
    ('/createquestion', CreateQuestion),
    ('/viewquestion', ViewQuestion),
    ('/createanswer', CreateAnswer),
    ('/editquestion', EditQuestion),
    ('/questionvote', QuestionVote),
    ('/answervote', AnswerVote),
    ('/search', Search),
    ('/upload', UploadHandler),
    ('/serve/([^/]+)?', ServeHandler),
], debug=True)