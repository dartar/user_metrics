#!/usr/bin/python

from flask import Flask, render_template, Markup # url_for, jsonify,
import src.etl.data_loader as dl

app = Flask(__name__)

@app.route('/')
def api_root():
    return 'Welcome to the user metrics API'

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/tag_definitions')
def tag_definitions():

    usertag_meta_data = ''
    conn = dl.Connector(instance='slave')
    conn._cur_.execute('select * from usertags_meta')

    for r in conn._cur_:
        usertag_meta_data += " ".join(dl.DataLoader().cast_elems_to_string(list(r))) + '<br>'

    return render_template('tag_definitions.html', data=Markup(usertag_meta_data))

@app.route('/cohorts')
def api_cohorts():
    conn = dl.Connector(instance='slave')
    conn._cur_.execute('select distinct utm_name from usertags_meta')
    return render_template('cohorts.html', data=[r[0] for r in conn._cur_])

@app.route('/metrics')
@app.route('/metrics/<cohort>')
def metrics(cohort):
    return 'Choose some metrics '


if __name__ == '__main__':
    app.run()
