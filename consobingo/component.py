from pathlib import Path
import streamlit.components.v1 as components
from .content import catalog
from .engine import public_state
component=components.declare_component('consobingo_game',path=str(Path(__file__).parent/'frontend'))

def play(game,*,ack='',message='',error='',demo=False,sync_error=False,disabled=False):
    return component(catalog=catalog(),state=public_state(game),ack=ack,message=message,error=error,demo=demo,sync_error=sync_error,disabled=disabled,key='cb_'+game['run_id'],default=None)
