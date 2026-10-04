"""Bilans personnels et suivi d’usage."""
from __future__ import annotations
import csv
from io import BytesIO, StringIO
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from .engine import summary
from .content import SECTION_LABELS


def _text(value):
    return escape(str(value if value is not None else '')).replace('\n','<br/>')

def build_pdf(game, profile=None):
    root=Path(__file__).parent/'fonts'
    if 'ConsoSans' not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont('ConsoSans',str(root/'DejaVuSans.ttf')))
        pdfmetrics.registerFont(TTFont('ConsoBold',str(root/'DejaVuSans-Bold.ttf')))
        pdfmetrics.registerFontFamily('ConsoSans',normal='ConsoSans',bold='ConsoBold',italic='ConsoSans',boldItalic='ConsoBold')
    styles=getSampleStyleSheet()
    for style in styles.byName.values(): style.fontName='ConsoSans'
    styles['Title'].fontName='ConsoBold';styles['Title'].fontSize=22;styles['Title'].alignment=TA_LEFT
    styles['Heading2'].fontName='ConsoBold';styles['Heading2'].fontSize=13
    styles['Heading2'].keepWithNext=True
    styles['BodyText'].fontSize=9.5;styles['BodyText'].leading=14
    styles['BodyText'].allowWidows=False;styles['BodyText'].allowOrphans=False
    styles.add(ParagraphStyle('SmallConso',parent=styles['BodyText'],fontSize=8,leading=11))
    p=lambda text,style='BodyText':Paragraph(_text(text),styles[style])
    flow=[p('ConsoBingo – mon carnet d’autoévaluation','Title'),p('Léa se remet en mouvement. Cas fictif.')]
    if profile:
        flow.append(p(' '.join(profile.get(k,'') for k in ('first_name','last_name')).strip()))
        flow.append(p(' · '.join(str(profile.get(k,'')) for k in ('promotion','campus','group_name')),'SmallConso'))
    flow.append(Spacer(1,.5*cm))
    table=[[p('Activité','SmallConso'),p('Repère personnel','SmallConso'),p('Essais','SmallConso')]]
    for row in summary(game):table.append([p(row['label'],'SmallConso'),p(row['status'],'SmallConso'),p(row['attempts'],'SmallConso')])
    t=Table(table,colWidths=[6.7*cm,7.3*cm,2*cm],repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.6,colors.black),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
    flow.extend([t,Spacer(1,.5*cm),p('Les indices et corrigés sont des ressources d’apprentissage. Tu peux reprendre le parcours, essayer une autre stratégie ou relancer une partie avec un ordre de présentation différent.')])
    for key,label in SECTION_LABELS.items():
        feedback=game['feedback'].get(key)
        if not feedback:continue
        block=[Spacer(1,.4*cm),p(label,'Heading2'),p(feedback['note'])]
        if feedback.get('extra'):block.append(p(feedback['extra']))
        errors=[i for i in feedback['items'] if not i['ok']]
        if errors:
            block.append(p('À reprendre à partir de ta dernière vérification :','SmallConso'))
            for i in errors:block.append(p(i['label']+' : '+i['detail'],'SmallConso'))
        else:block.append(p('Corrigé consulté. Reprends l’activité pour vérifier ton raisonnement.' if game['aids'].get(key)==3 else 'Les liens de ta dernière vérification sont cohérents.','SmallConso'))
        flow.append(KeepTogether(block))
    buffer=BytesIO()
    def footer(canvas,doc):
        canvas.saveState();canvas.setFont('ConsoSans',8);canvas.drawRightString(A4[0]-2.5*cm,1.3*cm,str(doc.page));canvas.restoreState()
    doc=SimpleDocTemplate(buffer,pagesize=A4,leftMargin=2.5*cm,rightMargin=2.5*cm,topMargin=2*cm,bottomMargin=2*cm,title='ConsoBingo - Bilan personnel',author='ConsoBingo')
    doc.build(flow,onFirstPage=footer,onLaterPages=footer)
    return buffer.getvalue()

def dashboard_rows(rows):
    result=[]
    for s in rows:
        learned=s.get('summary') or []
        out={'Matricule':s['student_id'],'Prénom':s['first_name'],'Nom':s['last_name'],'E-mail':s['email'],'Promotion':s['promotion'],'Campus':s['campus'],'Groupe':s['group_name'],'Parcours':'Bilan enregistré' if s.get('completed_at') else 'En cours' if s.get('started_at') else 'Non commencé','Activités explorées':sum(bool(x.get('checked')) for x in learned),'Dernière activité':s.get('updated_at') or ''}
        for x in learned:out[x['label']]=x['status']
        result.append(out)
    return result

def csv_export(rows):
    rows=dashboard_rows(rows)
    if not rows:return b''
    headers=list(dict.fromkeys(k for row in rows for k in row))
    out=StringIO();writer=csv.DictWriter(out,fieldnames=headers,delimiter=';');writer.writeheader()
    def safe(v):
        text=str(v if v is not None else '')
        return "'"+text if text.lstrip().startswith(('=','+','-','@')) else text
    writer.writerows({k:safe(v) for k,v in row.items()} for row in rows)
    return out.getvalue().encode('utf-8-sig')
