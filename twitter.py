from __future__ import division
from flask import Flask, Response, request, render_template
from socketio import socketio_manage
from socketio.namespace import BaseNamespace
import werkzeug
from werkzeug.serving import run_with_reloader
from socketio.server import SocketIOServer
from twython import TwythonStreamer
from gevent import monkey
from string import punctuation

monkey.patch_all()

app = Flask(__name__)
app.debug = True


@app.route("/")
def stream():
    """
    Main page
    """
    context = {"theword": "bird"}  # Supposed to send some information. Like analysis percentage of previously saved tweets.
    return render_template('main.html', **context)


class TweetsNamespace(BaseNamespace):
    sockets = {}

    def recv_connect(self):
        print "Got a socket connection"  # debug
        self.sockets[id(self)] = self

    def disconnect(self, *args, **kwargs):
        print "Got a socket disconnection"  # debug
        if id(self) in self.sockets:
            del self.sockets[id(self)]

        super(TweetsNamespace, self).disconnect(*args, **kwargs)
    # broadcast to all sockets on this channel!

    @classmethod
    def broadcast(self, event, message):
        for ws in self.sockets.values():
            ws.emit(event, message)


# Load Positive and Negative Dicts
pos_sent = open("words/positive.txt").read()
positive_words = pos_sent.split('\n')
positive_counts = []

neg_sent = open('words/negative.txt').read()
negative_words = neg_sent.split('\n')
negative_counts = []


# Twython Streaming Class
class TweetsStreamer(TwythonStreamer):
    def on_success(self, tweet):
        if 'text' in tweet:
            # First, send the text of the tweet as is
            TweetsNamespace.broadcast('tweet_text', tweet['text'])

            # Start the process by initing some vars
            positive_counter = 0
            negative_counter = 0

            # Lowercase the text of the tweet
            tweet_processed = tweet['text'].lower()

            # Strip from punctuation
            for p in list(punctuation):
                tweet_processed = tweet_processed.replace(p, '')

            words = tweet_processed.split(' ')
            word_count = len(words)

            for word in words:
                if word in positive_words:
                    positive_counter = positive_counter+1
                elif word in negative_words:
                    negative_counter = negative_counter+1

            pos = positive_counter / word_count
            neg = negative_counter / word_count

            TweetsNamespace.broadcast('sentiment_positive', pos)
            TweetsNamespace.broadcast('sentiment_negative', neg)

            # Adding Pos / Neg to Positive Counts and Negative Counts is NOT necessary for this app
            # it just provides a way for you to be able to generate a list of positive and negative counts
            # which can be zipped with the list of tweets later on. This would allow you to generate a CSV file (or other format you want)
            # at some point that can be used with analysis software.
            positive_counts.append(pos)
            negative_counts.append(neg)

    def on_error(self, status_code, data):
        print status_code, data


@app.route("/analyze", methods=["GET"])
def analyze():
    query = request.args.get('query', None)
    if query:
        # Authenticate the streamer
        # - Create a Twitter app
        # - Go to the OAuth settings tab
        # - Enter your keys below in the following order:
        #    - Consumer key
        #    - Consumer secret
        #    - Access token
        #    - Access token secret

        stream = TweetsStreamer('', '', '', '')

        TweetsNamespace.broadcast('tweet_text', 'Started Tracking... Waiting for tweets...')

        TweetsNamespace.broadcast('sentiment_positive', '1')
        TweetsNamespace.broadcast('sentiment_negative', '1')

        # Start tracking query
        # Note: In the demo, the analyize function is turned off so that it only captures "China".
        stream.statuses.filter(track=query)

        return Response("Started!")
    else:
        return Response("Please specify your message in the 'msg' parameter")


@app.route('/socket.io/<path:rest>')
def push_stream(rest):
    try:
        socketio_manage(request.environ, {'/tweets': TweetsNamespace}, request)
    except:
        app.logger.error("Exception while handling socketio connection", exc_info=True)


@werkzeug.serving.run_with_reloader  # Not necessary, but makes the server reload when you change the code.
def run_dev_server():
    app.debug = True
    port = 6020
    SocketIOServer(('', port), app, resource="socket.io").serve_forever()

if __name__ == "__main__":
    run_dev_server()