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
    app.text_input(key='auth_email').input(PROFILE['email']);app.button(key='auth_send').click().run()
    assert ('otp',PROFILE['email']) in cloud.calls
    app.text_input(key='auth_code').input('123456');app.button(key='auth_verify').click().run()
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
    app.text_input(key='auth_email').input('unknown@example.org');app.button(key='auth_send').click().run()
    assert not any(c[0]=='otp' for c in cloud.calls)
    assert app.error


def test_teacher_keeps_code_entry_and_role_after_send_and_rerun(monkeypatch):
    cloud=FakeCloud('teacher');app=prepare(monkeypatch,cloud)
    app.radio(key='auth_role').set_value('teacher').run()
    app.text_input(key='auth_email').input(PROFILE['email']);app.button(key='auth_send').click().run()
    assert app.success and not app.exception
    app.run()
    assert app.radio(key='auth_role').value=='teacher'
    assert app.text_input(key='auth_email').value==PROFILE['email']
    app.text_input(key='auth_code').input('123456');app.button(key='auth_verify').click().run()
    assert ('login',PROFILE['email'],'123456','teacher') in cloud.calls
    assert app.session_state['identity']['role']=='teacher'
    assert any(b.label=='Essayer le jeu en démo' for b in app.button)
    assert not app.exception


def test_received_code_can_be_used_after_send_timeout(monkeypatch):
    class SlowCloud(FakeCloud):
        def send_otp(self,email):
            super().send_otp(email)
            raise TimeoutError('private key must not be displayed')
    cloud=SlowCloud();app=prepare(monkeypatch,cloud)
    app.text_input(key='auth_email').input(PROFILE['email']);app.button(key='auth_send').click().run()
    assert 'ENVOI/DELAI' in app.warning[0].value
    assert 'private key' not in app.warning[0].value
    assert 'identity' not in app.session_state
    # A second request is throttled, but the code that already arrived remains usable.
    app.button(key='auth_send').click().run()
    assert len([c for c in cloud.calls if c[0]=='otp'])==1
    app.text_input(key='auth_code').input('123456');app.button(key='auth_verify').click().run()
    assert app.session_state['identity']['student_id']=='test'
    assert not app.exception


def test_code_can_be_verified_without_pending_state(monkeypatch):
    cloud=FakeCloud('teacher');app=prepare(monkeypatch,cloud)
    app.radio(key='auth_role').set_value('teacher').run()
    app.text_input(key='auth_email').input(PROFILE['email'])
    app.text_input(key='auth_code').input('123456');app.button(key='auth_verify').click().run()
    assert not any(c[0]=='otp' for c in cloud.calls)
    assert app.session_state['identity']['role']=='teacher'
    assert not app.exception


def test_rejected_code_keeps_form_and_does_not_authenticate(monkeypatch):
    cloud=FakeCloud();app=prepare(monkeypatch,cloud)
    app.text_input(key='auth_email').input(PROFILE['email'])
    app.text_input(key='auth_code').input('wrong');app.button(key='auth_verify').click().run()
    assert 'VALIDATION/' in app.error[0].value
    assert 'identity' not in app.session_state
    assert app.text_input(key='auth_email').value==PROFILE['email']
    assert app.text_input(key='auth_code')
    assert ('logout',) in cloud.calls
    assert not app.exception


def test_directory_failure_is_distinct_from_sending_and_stays_private(monkeypatch):
    class BrokenCloud(FakeCloud):
        def allowed(self,email,role):
            original=RuntimeError('private backend details')
            original.code='PGRST202'
            raise CloudError('Temporarily unavailable') from original
    cloud=BrokenCloud();app=prepare(monkeypatch,cloud)
    app.text_input(key='auth_email').input(PROFILE['email']);app.button(key='auth_send').click().run()
    assert 'ANNUAIRE/PGRST202' in app.error[0].value
    assert 'private' not in app.error[0].value
    assert not any(c[0]=='otp' for c in cloud.calls)
    assert 'identity' not in app.session_state
    assert app.text_input(key='auth_code')
    assert not app.exception


def test_identity_refusal_after_valid_code_never_opens_teacher_access(monkeypatch):
    class DeniedCloud(FakeCloud):
        def login(self,email,code,role):
            raise CloudError('Cette opération n’est pas autorisée pour ce compte.')
    cloud=DeniedCloud('teacher');app=prepare(monkeypatch,cloud)
    app.radio(key='auth_role').set_value('teacher').run()
    app.text_input(key='auth_email').input(PROFILE['email'])
    app.text_input(key='auth_code').input('123456');app.button(key='auth_verify').click().run()
    assert 'identity' not in app.session_state
    assert not any(b.label=='Essayer le jeu en démo' for b in app.button)
    assert ('logout',) in cloud.calls
    assert app.error and not app.exception


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
