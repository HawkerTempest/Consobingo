import copy
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
from streamlit.testing.v1 import AppTest
from consobingo.engine import new_game,summary
from consobingo.cloud import CloudError,ConflictError

APP=Path(__file__).parents[1]/'app.py'
PROFILE={'student_id':'test','email':'learner@example.org','first_name':'Léa','last_name':'Test','campus':'Campus','group_name':'A','promotion':'2026','active':True,'role':'student'}


class FakeCloud:
    def __init__(self,role='student'):
        self.role=role;self.row=None;self.calls=[]
    def allowed(self,email,role):self.calls.append(('allowed',email,role));return email=='learner@example.org'
    def send_otp(self,email):self.calls.append(('otp',email))
    def login(self,email,code,role):
        self.calls.append(('login',email,code,role))
        if code!='123456':raise CloudError('Invalid')
        return {**PROFILE,'role':self.role}
    def logout(self):self.calls.append(('logout',))
    def open_session(self):return str(uuid4())
    def get_run(self,*args):return self.row
    def claim(self,sid,initial=None):
        self.row={'state':copy.deepcopy(initial or new_game()),'revision':0,'cycle':1,'updated_at':'2026-10-04','started_at':'2026-10-04','completed_at':None}
        return self.row
    def touch(self,*args):return True
    def dashboard(self):return [{**PROFILE,'summary':[],'completed_at':None,'started_at':None}]


def prepare(monkeypatch,cloud):
    monkeypatch.setenv('CONSOBINGO_DEMO','false')
    monkeypatch.setenv('SUPABASE_URL','https://example.supabase.co')
    monkeypatch.setenv('SUPABASE_PUBLISHABLE_KEY','public-test-placeholder')
    app=AppTest.from_file(str(APP),default_timeout=15)
    app.session_state['store']=cloud
    return app.run()


def test_student_otp_and_start_with_shared_identity(monkeypatch):
    cloud=FakeCloud();app=prepare(monkeypatch,cloud)
    app.text_input[0].input(PROFILE['email']);app.button[0].click().run()
    assert ('otp',PROFILE['email']) in cloud.calls
    app.text_input[0].input('123456');app.button[0].click().run()
    assert app.session_state['identity']['student_id']=='test'
    next(b for b in app.button if b.label=='Commencer mon enquête').click().run()
    assert app.session_state['game']['app']=='ConsoBingo'
    assert not app.exception


def test_teacher_demo_uses_no_student_run(monkeypatch):
    cloud=FakeCloud('teacher');app=prepare(monkeypatch,cloud)
    app.session_state['identity']={**PROFILE,'role':'teacher'};app.run()
    assert not app.exception
    next(b for b in app.button if b.label=='Essayer le jeu en démo').click().run()
    assert app.session_state['demo'] and cloud.row is None
    assert not app.exception


def test_unknown_address_never_sends_code(monkeypatch):
    cloud=FakeCloud();app=prepare(monkeypatch,cloud)
    app.text_input[0].input('unknown@example.org');app.button[0].click().run()
    assert not any(c[0]=='otp' for c in cloud.calls)
    assert app.error


class State(dict):
    __getattr__=dict.__getitem__
    __setattr__=dict.__setitem__


def test_pending_save_retries_same_event_and_revision(monkeypatch):
    from consobingo import portal
    calls=[]
    class Store:
        def save(self,sid,revision,game,event,finish):
            calls.append((sid,revision,copy.deepcopy(game),event,finish))
            if len(calls)==1:raise CloudError('Offline')
            return {'revision':revision+1}
    g=new_game(22);state=State(game=g,cloud_session='session',cloud_row={'revision':4},demo=False)
    monkeypatch.setattr(portal,'st',SimpleNamespace(session_state=state))
    monkeypatch.setattr(portal,'store',lambda:Store())
    assert not portal.enqueue_save()
    assert 'sync_error' in state and 'save_packet' in state
    assert portal.try_save()
    assert calls[0]==calls[1] and state.cloud_row['revision']==5
    assert 'save_packet' not in state and 'sync_error' not in state


def test_conflict_keeps_unsaved_answers_for_rescue(monkeypatch):
    from consobingo import portal
    class Store:
        def save(self,*args):raise ConflictError('Other session')
    g=new_game(22);g['answers']['ekb']['d1']=0
    state=State(game=g,cloud_session='session',cloud_row={'revision':4},demo=False)
    monkeypatch.setattr(portal,'st',SimpleNamespace(session_state=state))
    monkeypatch.setattr(portal,'store',lambda:Store())
    assert not portal.enqueue_save()
    assert state.conflict and state.save_packet['state']['answers']['ekb']['d1']==0
