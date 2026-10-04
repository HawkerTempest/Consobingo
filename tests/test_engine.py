import copy
import json
import pytest
from consobingo import content as C
from consobingo import engine as E


def solved(section):
    game=E.new_game(2026)
    E.apply_solution(game,section)
    return game


@pytest.mark.parametrize('section',C.SECTION_LABELS)
def test_provided_corrections_are_consistent(section):
    g=solved(section)
    assert E.evaluate(g,section)['complete']
    assert not g['history']
    assert next(r for r in E.summary(g) if r['id']==section)['status']=='Corrigé consulté'


def test_six_main_factors_optional_seventh_and_two_causes():
    g=solved('factors')
    assert len(g['answers']['factors'])==6
    g['answers']['factors']['d1']=0
    assert E.evaluate(g,'factors')['complete']
    g['answers']['influence_links'][1]=g['answers']['influence_links'][0].copy()
    assert not E.evaluate(g,'factors')['complete']
    g['answers']['factors']['d1']=2
    assert any(not i['ok'] for i in E.evaluate(g,'factors')['items'] if i['key']=='d1')


def test_optional_closing_column_and_irrelevant_criterion():
    g=solved('table')
    g['answers']['criteria'].remove('close')
    assert E.evaluate(g,'table')['complete']
    g['answers']['criteria'].append('followers')
    for k,o in C.OFFERS.items():g['answers']['table'][k+'_followers']=str(o['followers'])
    assert not E.evaluate(g,'table')['complete']


@pytest.mark.parametrize('cell,bad',[('pulse_fee','36'),('tempo_coach','12')])
def test_price_component_and_paid_extra_traps(cell,bad):
    g=solved('table');g['answers']['table'][cell]=bad
    assert not next(i for i in E.evaluate(g,'table')['items'] if i['key']==cell)['ok']


def test_rules_are_applied_before_model_names_and_counterfactuals():
    g=E.new_game(1)
    assert not g['unlocked']
    g['answers']['rules']['either']['keep']=['atelier','tempo']
    assert E.record_check(g,'selection_either')['complete']
    assert g['unlocked']==['either']
    assert not g['history']
    g=solved('rule_all')
    g['answers']['rules']['all']['counter_keep']=['pulse','tempo']
    assert not E.evaluate(g,'rule_all')['complete']


def test_random_order_stable_on_resume_but_varied_across_runs():
    g=E.new_game(33);restored=json.loads(json.dumps(g))
    assert E.orders(g['seed'])==E.orders(restored['seed'])
    assert len({tuple(E.orders(i)['rules']) for i in range(30)})>3
    assert len({tuple(E.orders(i)['panels']) for i in range(20)})>10
    assert E.new_game(33)['run_id']!=g['run_id']


def test_nps_population_and_formula_help_are_not_prefilled():
    g=E.new_game(4)
    assert not g['answers']['metrics']['nps']['groups']
    assert g['answers']['metrics']['nps']['result']==''
    assert all('formula' not in m and 'result' not in m for m in C.catalog()['metrics'])
    first=E.hint(g,'metric_nps');second=E.hint(g,'metric_nps')
    assert first!=second and second==C.METRICS[0]['formula']
    g=solved('metric_nps');g['answers']['metrics']['nps']['data']['total']='42'
    r=E.evaluate(g,'metric_nps')
    assert not r['complete'] and 'passifs' in r['extra']
    assert sum(x['count'] for x in C.SURVEY.values())==60


def test_ltv_requires_margin_not_revenue():
    g=solved('metric_ltv');g['answers']['metrics']['ltv']['result']='702'
    r=E.evaluate(g,'metric_ltv')
    assert not r['complete'] and 'revenu' in r['extra']


def test_bonus_accepts_multiple_defensible_actions_and_two_obstacles():
    g=solved('bonus');g['answers']['bonus'][0]['action']='video'
    g['answers']['bonus'][1]['action']='late_trial'
    assert E.evaluate(g,'bonus')['complete']
    g['answers']['bonus'][1]=g['answers']['bonus'][0].copy()
    assert not E.evaluate(g,'bonus')['complete']


def test_solution_and_later_hint_never_become_autonomous_success():
    g=E.new_game(2);E.record_check(g,'ekb');first=copy.deepcopy(g['history']['ekb'][0])
    E.apply_solution(g,'ekb');E.hint(g,'ekb');E.record_check(g,'ekb')
    row=E.summary(g)[0]
    assert row['status']=='Corrigé consulté' and row['aided']
    assert g['history']['ekb'][0]==first


def test_repeated_checks_do_not_inflate_attempts_and_edits_expire_feedback():
    g=E.new_game(2);E.record_check(g,'ekb');E.record_check(g,'ekb')
    assert len(g['history']['ekb'])==1
    g['answers']['ekb']['d1']=0
    assert not E.summary(g)[0]['fresh']
    assert 'ekb' not in E.public_state(g)['fresh_feedback']


def test_first_attempt_survives_history_limit():
    g=E.new_game(2);E.record_check(g,'table');first=copy.deepcopy(g['history']['table'][0])
    for i in range(40):g['answers']['table']['pulse_fee']=str(i);E.record_check(g,'table')
    assert len(g['history']['table'])==E.MAX_ATTEMPTS
    assert g['history']['table'][0]==first


def test_browser_can_only_supply_editable_answers():
    g=E.new_game(2)
    event={'run_id':g['run_id'],'kind':'checkpoint','answers':g['answers'],'ui':{'screen':'table'},'feedback':{'ekb':{'complete':True}},'identity':{'role':'teacher'}}
    result,_=E.process_event(g,event)
    assert not result['feedback'] and 'identity' not in result
    with pytest.raises(ValueError):E.process_event(g,{**event,'run_id':'different'})


def test_finishing_does_not_lock_practice():
    g=E.new_game(2)
    g,_=E.process_event(g,{'run_id':g['run_id'],'kind':'finish','answers':g['answers']})
    a=copy.deepcopy(g['answers']);a['ekb']['d1']=0
    g,_=E.process_event(g,{'run_id':g['run_id'],'kind':'check','section':'ekb','answers':a})
    assert g['finished_at'] and g['answers']['ekb']['d1']==0


@pytest.mark.parametrize('value,expected',[('39 €',39),('10 %',10),('252,00',252),('1 200',1200),('−3',-3)])
def test_french_numeric_inputs(value,expected):assert E.same_number(value,expected)


@pytest.mark.parametrize('expression',["__import__('os').getcwd()",'2**30','1/0','float("inf")','[2][0]','True','9e999'])
def test_calculator_rejects_unsafe_or_invalid_expression(expression):
    with pytest.raises(ValueError):E.calculate(expression)


def test_calculator_handles_case_calculations():
    assert E.calculate('(30-12)/60*100')==30
    assert E.calculate('(36+3-25)*18')==252

