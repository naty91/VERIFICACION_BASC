import io, os, re, json, zipfile, hashlib, unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
    Image as RLImage, KeepTogether
)
from PIL import Image

st.set_page_config(page_title="CENASE | BASC Proveedores", page_icon="🛡️", layout="wide")

APP_VERSION = "2.0"
TODAY = date.today()
CENASE = {
    "razon": "CENTRO DE ASESORAMIENTO Y SEGURIDAD EMPRESARIAL CENASE CIA. LTDA.",
    "ruc": "0991317791001",
    "representante": "NELLI OLIMPIA GUAYGUA REYES",
    "cargo": "Gerente General",
    "direccion": "Cdla. Miraflores, Av. Guayas 303",
    "telefono": "044 608055",
    "correo": "bcamacho@cenase.ec; contador@cenase.ec",
    "web": "www.cenase.ec",
}

OFFICIAL_LINKS = {
    "SRI / Estado tributario": "https://srienlinea.sri.gob.ec/",
    "Superintendencia de Compañías": "https://appscvssoc.supercias.gob.ec/consultaCompanias/societario/busquedaCompanias.jsf",
    "Función Judicial": "https://procesosjudiciales.funcionjudicial.gob.ec/expel-busqueda-avanzada",
    "Fiscalía General del Estado": "https://www.fiscalia.gob.ec/consulta-de-noticias-del-delito/",
    "Consulta empresas BASC": "https://sibasc.wbasco.org/",
}

VERIFICATIONS = [
    "RUC / estado tributario SRI",
    "Superintendencia de Compañías",
    "Representante legal / administradores / accionistas / beneficiario final",
    "Función Judicial - proveedor",
    "Función Judicial - representante legal",
    "Fiscalía / fuentes oficiales - proveedor",
    "Fiscalía / fuentes oficiales - representante legal",
    "Listas restrictivas aplicables",
    "Noticias / adverse media",
    "Permisos / licencias sectoriales",
    "Referencias comerciales",
    "Certificación BASC (si aplica)",
]

EVAL_WEIGHTS = {
    "Existencia y legalidad": 15,
    "Verificación representante / estructura": 10,
    "Listas y debida diligencia": 20,
    "Reputación / antecedentes comerciales": 10,
    "Seguridad física / operativa": 15,
    "Seguridad de información": 10,
    "Gestión de personal": 10,
    "Subcontratación / terceros": 5,
    "Certificaciones / permisos": 5,
}

CHECKS = [
("Legalidad", "RUC actualizado, activo y verificado"),
("Legalidad", "Actividad económica coherente con el bien o servicio contratado"),
("Legalidad", "Razón social, dirección y datos de contacto verificados"),
("Legalidad", "Nombramiento vigente del representante legal, cuando aplique"),
("Legalidad", "Existencia/situación societaria verificada, cuando aplique"),
("Legalidad", "Permisos o licencias sectoriales vigentes, cuando aplique"),
("Conocimiento", "Formulario de conocimiento del proveedor completo"),
("Conocimiento", "Producto/servicio y alcance de la relación identificados"),
("Conocimiento", "Estructura societaria/beneficiario final revisado según riesgo"),
("Debida diligencia", "Consulta en fuentes/listas restrictivas aplicables documentada"),
("Debida diligencia", "Revisión de información pública adversa según riesgo"),
("Debida diligencia", "Sin inconsistencias relevantes entre documentos, actividad y servicio"),
("Debida diligencia", "Referencias comerciales verificadas cuando corresponda"),
("Seguridad BASC", "Nivel de criticidad/riesgo determinado"),
("Seguridad BASC", "Acceso a instalaciones CENASE/clientes evaluado"),
("Seguridad BASC", "Acceso a información confidencial/sensible evaluado"),
("Seguridad BASC", "Acceso a CCTV/GPS/sistemas/claves/monitoreo evaluado"),
("Seguridad BASC", "Manejo de uniformes/credenciales/radios/llaves evaluado"),
("Seguridad BASC", "Controles de acceso físico evaluados cuando corresponda"),
("Seguridad BASC", "Controles de protección de información evaluados cuando corresponda"),
("Personal/Terceros", "Uso de personal o subcontratistas declarado"),
("Personal/Terceros", "Selección/verificación de personal para actividades sensibles evaluada"),
("Personal/Terceros", "Retiro de accesos, credenciales, llaves y activos controlado"),
("Personal/Terceros", "Confidencialidad de personal con acceso sensible verificada"),
("Personal/Terceros", "Controles sobre subcontratistas/terceros evaluados"),
("Contratación", "Contrato, orden de servicio u otro documento formal existe"),
("Contratación", "Acuerdo/cláusulas de seguridad BASC aplicables"),
("Contratación", "Acuerdo/cláusula de confidencialidad cuando corresponda"),
("Contratación", "Obligación de reportar incidentes o actividades sospechosas"),
("Contratación", "Obligación de informar cambios relevantes del proveedor"),
("Evaluación", "Matriz de criticidad completada"),
("Evaluación", "Evaluación de cumplimiento completada"),
("Evaluación", "Proveedor aprobado por autoridad correspondiente"),
("Evaluación", "Hallazgos y acciones correctivas documentados"),
("Evaluación", "Próxima reevaluación definida"),
("Seguimiento", "Vigencia de documentos controlada"),
("Seguimiento", "Reevaluación periódica ejecutada según criticidad"),
("Seguimiento", "Reevaluación extraordinaria prevista ante incidentes/cambios"),
("Seguimiento", "Incidentes e incumplimientos registrados y cerrados"),
("Seguimiento", "Expediente conserva evidencia de las verificaciones"),
]

RISK_QUESTIONS = [
    ("access", "¿Tiene acceso a instalaciones de CENASE o de clientes?", 20),
    ("info", "¿Tiene acceso a información confidencial, sistemas, CCTV, GPS o claves?", 20),
    ("sensitive", "¿Maneja uniformes, credenciales, radios, llaves u otros elementos sensibles?", 20),
    ("continuity", "¿Su falla puede afectar significativamente la continuidad operativa o al cliente?", 15),
    ("subcontract", "¿Utiliza terceros/subcontratistas para prestar el servicio?", 10),
    ("regulated", "¿El servicio requiere permisos, licencias o habilitaciones especiales?", 10),
    ("scope", "¿Tiene relación relevante con operaciones dentro del alcance BASC?", 5),
]

SUPPLIER_STATUS = ["NUEVO", "EN VERIFICACIÓN", "APROBADO", "APROBADO CONDICIONADO", "BLOQUEADO", "INACTIVO"]
DECISIONS = ["PENDIENTE", "APROBADO", "APROBADO CONDICIONADO", "NO APROBADO / BLOQUEADO"]
RESULTS = ["PENDIENTE", "CONFORME", "SIN COINCIDENCIAS RELEVANTES", "CON ALERTA - REVISAR", "NO CONFORME", "NO APLICA"]

# ------------------------- UTILIDADES -------------------------
def norm(x):
    x = "" if x is None else str(x)
    x = ''.join(c for c in unicodedata.normalize('NFD', x) if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9]+', ' ', x.lower()).strip()

def clean_ruc(x):
    s = re.sub(r'\D', '', "" if x is None else str(x))
    return s[:13]

def safe_filename(x):
    s = unicodedata.normalize('NFKD', str(x or '')).encode('ascii','ignore').decode()
    s = re.sub(r'[^A-Za-z0-9._ -]+','',s).strip().replace(' ','_')
    return s[:100] or "SIN_NOMBRE"

def supplier_key(s):
    return clean_ruc(s.get("ruc", "")) or norm(s.get("razon", ""))

def empty_supplier():
    return {
        "ruc":"", "razon":"", "nombre_comercial":"", "tipo":"Jurídica", "representante":"",
        "contacto":"", "telefono":"", "email":"", "direccion":"", "ubicacion_fisica":"", "web":"",
        "servicio":"", "actividad_ruc":"", "inicio_operaciones":"", "inicio_servicio":"", "beneficiarios":"",
        "estado":"NUEVO", "responsable_cenase":"", "notas":""
    }

def missing_fields(s):
    req = [("RUC","ruc"),("Razón social","razon"),("Dirección","direccion"),("Teléfono","telefono"),
           ("Correo","email"),("Representante legal","representante"),("Producto/servicio","servicio")]
    return [label for label,key in req if not str(s.get(key,"" )).strip()]

def column_map(columns):
    aliases = {
        "ruc":["ruc","identificacion","cedula ruc","numero identificacion","documento"],
        "razon":["razon social","nombre razon social","persona","cliente proveedor","proveedor","nombre"],
        "nombre_comercial":["nombre comercial"], "tipo":["tipo persona","tipo","clase"],
        "representante":["representante legal","representante"], "contacto":["contacto","persona contacto"],
        "telefono":["telefono","telefonos","celular"], "email":["correo","email","e mail","correo electronico"],
        "direccion":["direccion","direccion principal"], "web":["pagina web","web"],
        "servicio":["servicio","producto servicio","actividad comercial","concepto"],
        "actividad_ruc":["actividad principal","actividad economica","actividad ruc"],
    }
    ncols={norm(c):c for c in columns}; out={}
    for target,als in aliases.items():
        for a in als:
            if norm(a) in ncols: out[target]=ncols[norm(a)]; break
        if target not in out:
            for nc,orig in ncols.items():
                if any(norm(a) in nc or nc in norm(a) for a in als): out[target]=orig; break
    return out

def load_suppliers(upload):
    name=upload.name.lower()
    if name.endswith('.csv'):
        upload.seek(0); df=pd.read_csv(upload,dtype=str,keep_default_na=False)
    else:
        upload.seek(0); xls=pd.ExcelFile(upload)
        # Selecciona la primera hoja con más columnas/filas útiles.
        best=None
        for sn in xls.sheet_names:
            tmp=pd.read_excel(xls,sheet_name=sn,dtype=str,keep_default_na=False)
            score=tmp.shape[0]*max(tmp.shape[1],1)
            if best is None or score>best[0]: best=(score,tmp)
        df=best[1]
    cmap=column_map(df.columns)
    rows=[]
    for _,r in df.iterrows():
        s=empty_supplier()
        for k,c in cmap.items(): s[k]=str(r.get(c,'')).strip()
        s['ruc']=clean_ruc(s['ruc'])
        if not s['razon'] and not s['ruc']: continue
        if s['tipo']:
            s['tipo']='Natural' if 'natural' in norm(s['tipo']) else 'Jurídica'
        rows.append(s)
    return pd.DataFrame(rows,columns=empty_supplier().keys())

def calc_risk(flags):
    score=sum(weight for key,_,weight in RISK_QUESTIONS if flags.get(key,False))
    label="CRÍTICA" if score>=75 else "ALTA" if score>=50 else "MEDIA" if score>=25 else "BAJA"
    return label,score

def due_date_by_risk(label, start=None):
    start=start or TODAY
    days={"CRÍTICA":365,"ALTA":365,"MEDIA":548,"BAJA":730}.get(label,365)
    return start+timedelta(days=days)

def calc_eval(evaluation):
    total=0.0; denominator=0.0
    for crit,w in EVAL_WEIGHTS.items():
        val=str(evaluation.get(crit,"PENDIENTE")).upper()
        if val=="NO APLICA": continue
        denominator += w
        if val=="CONFORME": total += w
        elif val=="PARCIAL": total += w*0.5
    pct = round((total/denominator*100),1) if denominator else 0.0
    return round(total,1), round(denominator,1), pct

def checklist_pct(checklist):
    applicable=[v for v in checklist.values() if v!="N/A"]
    if not applicable: return 0.0
    return round(sum(v=="CONFORME" for v in applicable)/len(applicable)*100,1)

def has_critical_alert(verifs):
    return any("ALERTA" in str(v.get("resultado","")) or str(v.get("resultado",""))=="NO CONFORME" for v in verifs.values())

def suggested_decision(s, ass):
    _,_,eval_pct=calc_eval(ass.get("evaluation",{}))
    chk=checklist_pct(ass.get("checklist",{}))
    if has_critical_alert(ass.get("verifs",{})): return "NO APROBADO / BLOQUEADO"
    if missing_fields(s): return "PENDIENTE"
    if eval_pct>=80 and chk>=80: return "APROBADO"
    if eval_pct>=60 and chk>=60: return "APROBADO CONDICIONADO"
    return "PENDIENTE"

def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()

def assessment_without_binary(ass):
    return {k:v for k,v in ass.items() if k not in ("croquis_bytes","foto_bytes")}

def serialize_state():
    suppliers=st.session_state.suppliers.fillna("").to_dict('records')
    assess={k:assessment_without_binary(v) for k,v in st.session_state.assess.items()}
    history=st.session_state.history
    actions=st.session_state.actions
    return {"app_version":APP_VERSION,"exported_at":datetime.now().isoformat(),"suppliers":suppliers,
            "assess":jsonable(assess),"history":jsonable(history),"actions":jsonable(actions)}

def jsonable(obj):
    if isinstance(obj,(date,datetime)): return obj.isoformat()
    if isinstance(obj,dict): return {str(k):jsonable(v) for k,v in obj.items()}
    if isinstance(obj,list): return [jsonable(v) for v in obj]
    return obj

def export_backup_zip():
    buf=io.BytesIO(); manifest={"evidence":[],"media":[]}
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr("CENASE_BASC_BACKUP.json",json.dumps(serialize_state(),ensure_ascii=False,indent=2))
        for n,(key,items) in enumerate(st.session_state.evidence.items()):
            for j,it in enumerate(items):
                path=f"evidencias/{n}/{j}_{safe_filename(it['name'])}"; z.writestr(path,it['bytes'])
                manifest["evidence"].append({"key":key,"path":path,"name":it['name'],"uploaded_at":it.get('uploaded_at','')})
        for n,(key,ass) in enumerate(st.session_state.assess.items()):
            for field in ("croquis_bytes","foto_bytes"):
                if ass.get(field):
                    path=f"media/{n}/{field}.jpg"; z.writestr(path,ass[field]); manifest["media"].append({"key":key,"field":field,"path":path})
        z.writestr("MANIFEST.json",json.dumps(manifest,ensure_ascii=False,indent=2))
    buf.seek(0); return buf.getvalue()

def import_backup_zip(upload):
    upload.seek(0)
    with zipfile.ZipFile(upload) as z:
        data=json.loads(z.read("CENASE_BASC_BACKUP.json").decode('utf-8'))
        manifest=json.loads(z.read("MANIFEST.json").decode('utf-8')) if "MANIFEST.json" in z.namelist() else {"evidence":[],"media":[]}
        st.session_state.suppliers=pd.DataFrame(data.get('suppliers',[]),columns=empty_supplier().keys())
        st.session_state.assess=data.get('assess',{})
        st.session_state.history=data.get('history',{})
        st.session_state.actions=data.get('actions',{})
        ev={}
        for item in manifest.get("evidence",[]):
            raw=z.read(item["path"]); key=item["key"]
            ev.setdefault(key,[]).append({"name":item.get('name','evidencia'),"bytes":raw,"sha256":sha256_bytes(raw),"uploaded_at":item.get('uploaded_at','')})
        st.session_state.evidence=ev
        for item in manifest.get("media",[]):
            key=item["key"]; st.session_state.assess.setdefault(key,{})[item["field"]]=z.read(item["path"])

# ------------------------- PDF -------------------------
styles=getSampleStyleSheet()
TITLE=ParagraphStyle('T',parent=styles['Title'],fontName='Helvetica-Bold',fontSize=13,leading=16,alignment=TA_CENTER,textColor=colors.HexColor('#17365D'),spaceAfter=10)
H1=ParagraphStyle('H1x',parent=styles['Heading2'],fontName='Helvetica-Bold',fontSize=10,leading=12,textColor=colors.HexColor('#17365D'),spaceBefore=7,spaceAfter=4)
BODY=ParagraphStyle('Bodyx',parent=styles['BodyText'],fontName='Helvetica',fontSize=8.2,leading=10.5,alignment=TA_JUSTIFY,spaceAfter=5)
SMALL=ParagraphStyle('Small',parent=BODY,fontSize=7.1,leading=8.8)
CENTER=ParagraphStyle('Center',parent=BODY,alignment=TA_CENTER)

def ptxt(x):
    x="" if x is None else str(x)
    return x.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('\n','<br/>')

def header_footer(canvas,doc):
    canvas.saveState(); w,h=A4
    canvas.setFont('Helvetica-Bold',7); canvas.setFillColor(colors.HexColor('#17365D'))
    canvas.drawString(1.35*cm,0.75*cm,'CENASE CIA. LTDA. - SGCS BASC | Asociados de Negocio')
    canvas.setFont('Helvetica',7); canvas.drawRightString(w-1.35*cm,0.75*cm,f'Página {doc.page}')
    canvas.restoreState()

def info_table(s):
    rows=[
      ["Razón social",s.get('razon',''),"RUC",s.get('ruc','')],
      ["Nombre comercial",s.get('nombre_comercial',''),"Persona",s.get('tipo','')],
      ["Representante legal",s.get('representante',''),"Contacto",s.get('contacto','')],
      ["Dirección legal",s.get('direccion',''),"Ubicación física",s.get('ubicacion_fisica','')],
      ["Teléfono",s.get('telefono',''),"Correo",s.get('email','')],
      ["Página web",s.get('web',''),"Inicio operaciones",s.get('inicio_operaciones','')],
      ["Inicio servicio CENASE",s.get('inicio_servicio',''),"Servicio",s.get('servicio','')],
      ["Actividad principal RUC",s.get('actividad_ruc',''),"Estado",s.get('estado','')],
    ]
    data=[[Paragraph(f'<b>{ptxt(a)}</b>',SMALL),Paragraph(ptxt(b),SMALL),Paragraph(f'<b>{ptxt(c)}</b>',SMALL),Paragraph(ptxt(d),SMALL)] for a,b,c,d in rows]
    t=Table(data,colWidths=[2.6*cm,5.2*cm,2.5*cm,6.1*cm])
    t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),0.3,colors.HexColor('#B4C7E7')),('BACKGROUND',(0,0),(0,-1),colors.HexColor('#D9EAF7')),('BACKGROUND',(2,0),(2,-1),colors.HexColor('#D9EAF7')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),3),('RIGHTPADDING',(0,0),(-1,-1),3)]))
    return t

def image_flowable(raw,max_w=7.5*cm,max_h=6.5*cm):
    if not raw: return Paragraph("<i>Sin imagen adjunta.</i>",SMALL)
    try:
        bio=io.BytesIO(raw); im=Image.open(bio); w,h=im.size
        ratio=min(max_w/w,max_h/h); bio.seek(0)
        return RLImage(bio,width=w*ratio,height=h*ratio)
    except Exception:
        return Paragraph("<i>Archivo adjunto no compatible como imagen.</i>",SMALL)

def signature_table(s, ass):
    verifier=ass.get('verified_by','') or s.get('responsable_cenase','') or 'Responsable CENASE'
    approver=ass.get('approved_by','') or 'Aprobador autorizado CENASE'
    return Table([
        [Paragraph("<b>ELABORADO / VERIFICADO POR</b>",CENTER),Paragraph("<b>APROBADO POR</b>",CENTER),Paragraph("<b>ASOCIADO DE NEGOCIO</b>",CENTER)],
        ["\n\n________________________","\n\n________________________","\n\n________________________"],
        [Paragraph(ptxt(verifier),CENTER),Paragraph(ptxt(approver),CENTER),Paragraph(ptxt(s.get('representante') or s.get('razon')),CENTER)],
        [Paragraph(ptxt(ass.get('verified_date','')),CENTER),Paragraph(ptxt(ass.get('approval_date','')),CENTER),Paragraph("Fecha: __________________",CENTER)],
    ],colWidths=[5.5*cm,5.5*cm,5.5*cm])

def build_pdf(s,kind="expediente",ass=None,evidence_items=None):
    ass=ass or {}; evidence_items=evidence_items or []
    risk=ass.get('risk') or {'label':'BAJA','score':0,'next':due_date_by_risk('BAJA')}
    checklist=ass.get('checklist',{}); verifs=ass.get('verifs',{}); evaluation=ass.get('evaluation',{})
    buf=io.BytesIO(); doc=SimpleDocTemplate(buf,pagesize=A4,rightMargin=1.35*cm,leftMargin=1.35*cm,topMargin=1.25*cm,bottomMargin=1.25*cm)
    titlemap={"conf":"ACUERDO DE CONFIDENCIALIDAD Y PROTECCIÓN DE DATOS PERSONALES","seguridad":"ACUERDO DE SEGURIDAD COMO ASOCIADO DE NEGOCIO BASC","verificacion":"REGISTRO DE VERIFICACIÓN DE ASOCIADOS DE NEGOCIO","evaluacion":"EVALUACIÓN Y CRITICIDAD DEL ASOCIADO DE NEGOCIO","plan":"PLAN DE ACCIÓN DEL ASOCIADO DE NEGOCIO","expediente":"EXPEDIENTE BASC COMPLETO DEL ASOCIADO DE NEGOCIO"}
    story=[Paragraph(titlemap[kind],TITLE),info_table(s),Spacer(1,7)]

    def conf_section():
        return [
            Paragraph("PRIMERA: OBJETO",H1),Paragraph(f"El presente acuerdo tiene por objeto garantizar el secreto, confidencialidad y uso lícito de la información y datos personales a los que <b>{ptxt(s.get('razon','EL PROVEEDOR'))}</b> tenga acceso con ocasión de los bienes o servicios suministrados a CENASE.",BODY),
            Paragraph("SEGUNDA: CONFIDENCIALIDAD",H1),Paragraph("EL PROVEEDOR reconoce como confidencial la información comercial, técnica, financiera, listados, planes de seguridad, vulnerabilidades, claves de acceso, estrategias, bases de datos y demás información no pública de CENASE. Se obliga a utilizarla únicamente para el objeto de la relación, no divulgarla ni transferirla sin autorización y mantener reserva aun después de terminada la relación.",BODY),
            Paragraph("TERCERA: PROTECCIÓN DE DATOS PERSONALES",H1),Paragraph("Cuando la prestación implique tratamiento de datos personales, EL PROVEEDOR deberá tratar los datos únicamente para la finalidad autorizada, limitar accesos, aplicar medidas técnicas y organizativas apropiadas, comunicar incidentes de seguridad sin dilación indebida y devolver o eliminar la información al concluir la finalidad, salvo obligación legal de conservación.",BODY),
            Paragraph("CUARTA: INCIDENTES Y RESPONSABILIDAD",H1),Paragraph("EL PROVEEDOR informará cualquier pérdida, acceso no autorizado, alteración, divulgación o uso indebido de información y colaborará con las medidas de contención, investigación y remediación. Responderá por incumplimientos atribuibles a su actuación, personal o subcontratistas conforme al contrato y la normativa aplicable.",BODY),
            Paragraph("QUINTA: COMUNICACIONES",H1),Paragraph(f"PROVEEDOR: {ptxt(s.get('direccion',''))} | {ptxt(s.get('telefono',''))} | {ptxt(s.get('email',''))}. CENASE: {CENASE['direccion']} | {CENASE['telefono']} | {CENASE['correo']}.",BODY),
            Spacer(1,18),signature_table(s,ass)
        ]

    def security_section():
        bullets=[
            "Cumplir los requisitos legales, contractuales y de seguridad aplicables al servicio contratado.",
            "Proteger instalaciones, información, credenciales, uniformes, radios, llaves, sistemas, equipos y demás activos a los que tenga acceso.",
            "Prevenir actividades ilícitas, fraude, corrupción, soborno, contrabando y conductas que comprometan la seguridad de la operación.",
            "Aplicar controles proporcionales de selección, identificación y seguimiento del personal asignado a actividades sensibles.",
            "Retirar accesos, credenciales, llaves, equipos e información cuando el personal deje de participar en el servicio.",
            "Reportar inmediatamente incidentes, actividades sospechosas, pérdidas, accesos no autorizados y cambios relevantes que puedan afectar la seguridad.",
            "Informar y controlar subcontratistas o terceros que intervengan en actividades sensibles, según lo establecido contractualmente.",
            "Conservar evidencias que permitan demostrar el cumplimiento de los controles aplicables y atender verificaciones acordadas con CENASE.",
        ]
        x=[Paragraph("COMPROMISO DE SEGURIDAD",H1),Paragraph("CENASE mantiene un Sistema de Gestión en Control y Seguridad y gestiona a sus asociados de negocio de acuerdo con su criticidad y exposición al riesgo.",BODY)]
        x += [Paragraph(f"• {b}",BODY) for b in bullets]
        x += [Paragraph(f"Nivel de criticidad registrado para este asociado: <b>{risk.get('label','PENDIENTE')}</b> ({risk.get('score',0)}/100).",BODY),Spacer(1,15),signature_table(s,ass)]
        return x

    def verification_section():
        x=[Paragraph("1. INFORMACIÓN GENERAL",H1)]
        x.append(Paragraph(f"Beneficiarios finales / estructura relevante: {ptxt(s.get('beneficiarios','') or 'PENDIENTE')}",BODY))
        x.append(Paragraph("2. CROQUIS Y FOTOGRAFÍA DE UBICACIÓN",H1))
        croquis=ass.get('croquis_bytes'); foto=ass.get('foto_bytes')
        tab=Table([[image_flowable(croquis),image_flowable(foto)]],[8.1*cm,8.1*cm])
        tab.setStyle(TableStyle([('BOX',(0,0),(-1,-1),0.5,colors.grey),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('ALIGN',(0,0),(-1,-1),'CENTER')]))
        x.append(tab)
        x.append(Paragraph("3. PREGUNTAS ESPECÍFICAS DEL REGISTRO",H1))
        qrows=[["Control","Resultado"]]
        qrows += [
            ["¿La empresa cuenta con certificado BASC?",ass.get('has_basc','PENDIENTE')],
            ["¿Tiene acceso a instalaciones de la empresa?","Sí" if ass.get('access') else "No"],
            ["¿Tiene acceso a información confidencial?","Sí" if ass.get('info') else "No"],
            ["¿Tiene suscrito contrato mercantil o acuerdo de confidencialidad con CENASE?",ass.get('has_contract','PENDIENTE')],
            ["¿Se constató el estado tributario en el SRI?",verifs.get('RUC / estado tributario SRI',{}).get('resultado','PENDIENTE')],
            ["¿Se consultó información societaria/representantes/beneficiarios finales en Supercias?",verifs.get('Superintendencia de Compañías',{}).get('resultado','PENDIENTE')],
            ["¿Se verificaron posibles procesos en Función Judicial?",verifs.get('Función Judicial - proveedor',{}).get('resultado','PENDIENTE')],
            ["¿Se verificaron noticias del delito / fuentes de Fiscalía?",verifs.get('Fiscalía / fuentes oficiales - proveedor',{}).get('resultado','PENDIENTE')],
        ]
        qt=Table([[Paragraph(ptxt(c),SMALL) for c in row] for row in qrows],colWidths=[12.6*cm,3.6*cm],repeatRows=1)
        qt.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#4472C4')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),0.3,colors.grey),('VALIGN',(0,0),(-1,-1),'TOP')]))
        x.append(qt)
        x.append(Paragraph("4. VERIFICACIONES Y EVIDENCIAS",H1))
        rows=[["Consulta","Resultado","Fecha","Evidencia / Observación"]]
        for k in VERIFICATIONS:
            v=verifs.get(k,{})
            rows.append([k,v.get('resultado','PENDIENTE'),str(v.get('fecha','')),v.get('evidencia','')])
        t=Table([[Paragraph(ptxt(c),SMALL) for c in row] for row in rows],colWidths=[4.3*cm,3.1*cm,2.4*cm,6.4*cm],repeatRows=1)
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#4472C4')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),0.25,colors.grey),('VALIGN',(0,0),(-1,-1),'TOP')]))
        x.append(t)
        x.append(Paragraph("5. RESULTADO DE LA EVALUACIÓN: NIVEL DE CRITICIDAD",H1))
        x.append(Paragraph(f"De acuerdo con la información registrada, el asociado de negocio presenta criticidad <b>{risk.get('label','PENDIENTE')}</b>, con puntaje {risk.get('score',0)}/100. Fecha de evaluación: {ptxt(ass.get('verified_date','PENDIENTE'))}.",BODY))
        x.append(Spacer(1,10)); x.append(signature_table(s,ass))
        return x

    def evaluation_section():
        total,den,pct=calc_eval(evaluation)
        rows=[["Criterio","Peso","Resultado"]]
        for k,w in EVAL_WEIGHTS.items(): rows.append([k,str(w),evaluation.get(k,'PENDIENTE')])
        rows.append(["RESULTADO",f"{total:.1f}/{den:.1f}",f"{pct:.1f}%"])
        t=Table([[Paragraph(ptxt(c),SMALL) for c in row] for row in rows],colWidths=[9.2*cm,2.4*cm,4.8*cm],repeatRows=1)
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#4472C4')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),0.3,colors.grey),('VALIGN',(0,0),(-1,-1),'TOP')]))
        decision=ass.get('decision') or suggested_decision(s,ass)
        return [Paragraph("EVALUACIÓN DE CUMPLIMIENTO",H1),t,Spacer(1,6),Paragraph(f"Criticidad: <b>{risk.get('label')}</b> ({risk.get('score')}/100). Cumplimiento de evaluación: <b>{pct:.1f}%</b>. Checklist: <b>{checklist_pct(checklist):.1f}%</b>. Decisión registrada/sugerida: <b>{ptxt(decision)}</b>.",BODY),Paragraph("Una alerta crítica debe analizarse de forma independiente y puede impedir la aprobación aunque el porcentaje global sea alto.",BODY)]

    def checklist_section():
        rows=[["#","Categoría","Control","Estado"]]
        for i,(cat,control) in enumerate(CHECKS,1): rows.append([str(i),cat,control,checklist.get(str(i),'PENDIENTE')])
        t=Table([[Paragraph(ptxt(c),SMALL) for c in row] for row in rows],colWidths=[0.7*cm,2.8*cm,10.3*cm,2.6*cm],repeatRows=1)
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#4472C4')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),0.25,colors.grey),('VALIGN',(0,0),(-1,-1),'TOP')]))
        return [Paragraph("CHECKLIST BASC",H1),t]

    def action_section():
        actions=st.session_state.actions.get(supplier_key(s),[]) if 'actions' in st.session_state else []
        rows=[["Hallazgo / acción","Responsable","Fecha compromiso","Estado","Cierre"]]
        for a in actions: rows.append([a.get('hallazgo',''),a.get('responsable',''),a.get('fecha_compromiso',''),a.get('estado',''),a.get('fecha_cierre','')])
        if len(rows)==1: rows.append(["Sin acciones registradas.","","","",""])
        t=Table([[Paragraph(ptxt(c),SMALL) for c in row] for row in rows],colWidths=[6.7*cm,3.0*cm,2.5*cm,2.0*cm,2.0*cm],repeatRows=1)
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#4472C4')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),0.25,colors.grey),('VALIGN',(0,0),(-1,-1),'TOP')]))
        return [Paragraph("PLAN DE ACCIÓN / HALLAZGOS",H1),t]

    def evidence_index():
        rows=[["Archivo","SHA-256","Fecha carga"]]
        for e in evidence_items: rows.append([e.get('name',''),e.get('sha256','')[:20]+'…',e.get('uploaded_at','')])
        if len(rows)==1: rows.append(["Sin archivos adjuntos.","",""])
        t=Table([[Paragraph(ptxt(c),SMALL) for c in row] for row in rows],colWidths=[7.0*cm,5.5*cm,3.7*cm],repeatRows=1)
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#4472C4')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),0.25,colors.grey)]))
        return [Paragraph("ÍNDICE DE EVIDENCIAS DIGITALES",H1),t]

    if kind=="conf": story+=conf_section()
    elif kind=="seguridad": story+=security_section()
    elif kind=="verificacion": story+=verification_section()
    elif kind=="evaluacion": story+=evaluation_section()
    elif kind=="plan": story+=action_section()
    else:
        story += verification_section()+[PageBreak()]+evaluation_section()+[PageBreak()]+checklist_section()+[PageBreak()]+action_section()+[PageBreak()]+evidence_index()+[PageBreak()]+conf_section()+[PageBreak()]+security_section()
    doc.build(story,onFirstPage=header_footer,onLaterPages=header_footer)
    return buf.getvalue()

# ------------------------- REPORTES -------------------------
def report_rows():
    rows=[]
    for _,row in st.session_state.suppliers.iterrows():
        s=row.to_dict(); key=supplier_key(s); ass=st.session_state.assess.get(key,{})
        risk=ass.get('risk',{'label':'PENDIENTE','score':0,'next':''})
        total,den,epct=calc_eval(ass.get('evaluation',{})); cpct=checklist_pct(ass.get('checklist',{}))
        decision=ass.get('decision','PENDIENTE')
        actions=st.session_state.actions.get(key,[])
        open_actions=sum(a.get('estado')!='CERRADO' for a in actions)
        next_date=str(risk.get('next',''))
        due="SIN FECHA"
        try:
            nd=date.fromisoformat(next_date[:10]); delta=(nd-TODAY).days
            due="VENCIDO" if delta<0 else "POR VENCER" if delta<=30 else "VIGENTE"
        except Exception: pass
        rows.append({
            'RUC':s.get('ruc'),'Proveedor':s.get('razon'),'Servicio':s.get('servicio'),'Estado proveedor':s.get('estado'),
            'Criticidad':risk.get('label'),'Puntaje riesgo':risk.get('score'),'% Evaluación':epct,'% Checklist':cpct,
            'Decisión':decision,'Responsable verificación':ass.get('verified_by',''),'Aprobador':ass.get('approved_by',''),
            'Última revisión':ass.get('verified_date',''),'Próxima revisión':next_date,'Vigencia':due,
            'Alertas críticas':'SÍ' if has_critical_alert(ass.get('verifs',{})) else 'NO','Acciones abiertas':open_actions,
            'Evidencias':len(st.session_state.evidence.get(key,[])),'Pendientes datos':', '.join(missing_fields(s))
        })
    return rows

def make_report_excel(records):
    out=io.BytesIO(); df=pd.DataFrame(records)
    with pd.ExcelWriter(out,engine='xlsxwriter') as writer:
        df.to_excel(writer,index=False,sheet_name='Maestro BASC')
        wb=writer.book; ws=writer.sheets['Maestro BASC']
        head=wb.add_format({'bold':True,'font_color':'white','bg_color':'#4472C4','border':1,'align':'center','valign':'vcenter','text_wrap':True})
        pct=wb.add_format({'num_format':'0.0','align':'center'})
        for c,col in enumerate(df.columns):
            ws.write(0,c,col,head); width=min(max(12,len(str(col))+2),34); ws.set_column(c,c,width)
        if len(df):
            ws.autofilter(0,0,len(df),len(df.columns)-1); ws.freeze_panes(1,0)
            for col in ['% Evaluación','% Checklist']:
                if col in df.columns: ws.set_column(df.columns.get_loc(col),df.columns.get_loc(col),14,pct)
            if 'Vigencia' in df.columns:
                c=df.columns.get_loc('Vigencia'); ws.conditional_format(1,c,len(df),c,{'type':'text','criteria':'containing','value':'VENCIDO','format':wb.add_format({'bg_color':'#FFC7CE','font_color':'#9C0006'})})
                ws.conditional_format(1,c,len(df),c,{'type':'text','criteria':'containing','value':'POR VENCER','format':wb.add_format({'bg_color':'#FFEB9C','font_color':'#9C6500'})})
    out.seek(0); return out.getvalue()

def supplier_package(s,ass,key):
    zbuf=io.BytesIO(); folder=f"{clean_ruc(s.get('ruc'))}_{safe_filename(s.get('razon'))}"
    with zipfile.ZipFile(zbuf,'w',zipfile.ZIP_DEFLATED) as z:
        docs=[('conf','01_Acuerdo_Confidencialidad.pdf'),('seguridad','02_Acuerdo_Seguridad_BASC.pdf'),('verificacion','03_Registro_Verificacion.pdf'),('evaluacion','04_Evaluacion_Criticidad.pdf'),('plan','05_Plan_Accion.pdf'),('expediente','06_Expediente_BASC_Completo.pdf')]
        evidence=st.session_state.evidence.get(key,[])
        for kind,nm in docs: z.writestr(f"{folder}/{nm}",build_pdf(s,kind,ass,evidence))
        for e in evidence: z.writestr(f"{folder}/EVIDENCIAS/{safe_filename(e['name'])}",e['bytes'])
        z.writestr(f"{folder}/07_Ficha_Digital.json",json.dumps(jsonable({'proveedor':s,'evaluacion':ass,'acciones':st.session_state.actions.get(key,[])}),ensure_ascii=False,indent=2))
    zbuf.seek(0); return zbuf.getvalue()

# ------------------------- SESIÓN -------------------------
if 'suppliers' not in st.session_state: st.session_state.suppliers=pd.DataFrame(columns=empty_supplier().keys())
if 'assess' not in st.session_state: st.session_state.assess={}
if 'history' not in st.session_state: st.session_state.history={}
if 'actions' not in st.session_state: st.session_state.actions={}
if 'evidence' not in st.session_state: st.session_state.evidence={}

# ------------------------- LOGIN OPCIONAL -------------------------
def authenticate():
    try:
        configured=bool(st.secrets.get('auth',{}).get('username'))
    except Exception: configured=False
    if not configured: return True
    if st.session_state.get('authenticated'): return True
    st.title("🛡️ CENASE | Acceso BASC")
    u=st.text_input("Usuario"); p=st.text_input("Contraseña",type='password')
    if st.button("Ingresar",type='primary'):
        auth=st.secrets['auth']
        if u==auth['username'] and p==auth['password']:
            st.session_state.authenticated=True; st.rerun()
        else: st.error("Credenciales incorrectas.")
    st.stop()
authenticate()

st.markdown("""
<style>
.block-container{padding-top:1.1rem}.stTabs [data-baseweb=tab]{font-weight:650}.card{padding:14px;border:1px solid #dbe3ef;border-radius:12px;background:#f8fbff}.big{font-size:1.45rem;font-weight:700;color:#17365D}.ok{color:#14823b;font-weight:700}.warn{color:#9c6500;font-weight:700}.bad{color:#9c0006;font-weight:700}
</style>
""",unsafe_allow_html=True)
st.title("🛡️ CENASE | Gestión BASC de Asociados de Negocio")
st.caption(f"Versión {APP_VERSION} · Proveedores · Verificación · Evidencias · Acuerdos · Planes de acción · Expedientes · Historial · Reporte maestro")

with st.sidebar:
    st.subheader("🔐 Seguridad y respaldo")
    st.info("Si la app se publica en Streamlit Community Cloud, usa el respaldo ZIP para conservar información y evidencias. Para un entorno corporativo permanente conviene conectar posteriormente una base de datos/almacenamiento privado.")
    st.download_button("⬇️ Respaldo completo",export_backup_zip(),f"CENASE_BASC_BACKUP_{TODAY}.zip","application/zip")
    restore=st.file_uploader("Restaurar respaldo ZIP",type=['zip'],key='restore')
    if restore and st.button("Restaurar ahora"):
        try: import_backup_zip(restore); st.success("Respaldo restaurado."); st.rerun()
        except Exception as e: st.error(f"No se pudo restaurar: {e}")
    st.divider(); st.subheader("🔗 Consultas oficiales")
    for label,url in OFFICIAL_LINKS.items(): st.link_button(label,url,use_container_width=True)
    st.caption("La app registra la evidencia de la consulta; no declara resultados externos que no hayan sido verificados por el responsable.")

T1,T2,T3,T4,T5,T6=st.tabs(["📥 Proveedores","👤 Expediente","🔎 Verificación BASC","🧯 Acciones / Historial","📄 Documentos masivos","📊 Dashboard"])

with T1:
    c1,c2=st.columns([2,1])
    with c1:
        up=st.file_uploader("Cargar listado masivo Excel o CSV",type=['xlsx','xls','csv'],key='bulk')
        if up:
            try:
                df=load_suppliers(up); st.success(f"Se detectaron {len(df)} proveedores."); st.dataframe(df.head(40),use_container_width=True,hide_index=True)
                if st.button("Agregar / actualizar base",type='primary'):
                    old=st.session_state.suppliers.copy(); combo=pd.concat([old,df],ignore_index=True)
                    combo['_key']=combo.apply(lambda r:supplier_key(r.to_dict()),axis=1)
                    combo=combo[combo['_key']!=''].drop_duplicates('_key',keep='last').drop(columns=['_key'])
                    st.session_state.suppliers=combo.reset_index(drop=True); st.success("Base actualizada."); st.rerun()
            except Exception as e: st.error(f"No pude leer el archivo: {e}")
    with c2:
        st.metric("Proveedores",len(st.session_state.suppliers))
        st.download_button("CSV normalizado",st.session_state.suppliers.to_csv(index=False).encode('utf-8-sig'),"base_proveedores_cenase.csv","text/csv")
    st.divider(); st.subheader("Ingreso individual")
    with st.form('new_supplier'):
        a,b,c=st.columns(3); razon=a.text_input("Razón social *"); ruc=b.text_input("RUC *"); tipo=c.selectbox("Persona",["Jurídica","Natural"])
        a,b,c=st.columns(3); rep=a.text_input("Representante legal"); contacto=b.text_input("Contacto"); servicio=c.text_input("Producto / servicio *")
        a,b,c=st.columns(3); direccion=a.text_input("Dirección"); tel=b.text_input("Teléfono"); email=c.text_input("Correo")
        if st.form_submit_button("Guardar proveedor",type='primary'):
            row=empty_supplier(); row.update({'razon':razon,'ruc':clean_ruc(ruc),'tipo':tipo,'representante':rep,'contacto':contacto,'servicio':servicio,'direccion':direccion,'telefono':tel,'email':email})
            st.session_state.suppliers=pd.concat([st.session_state.suppliers,pd.DataFrame([row])],ignore_index=True); st.success("Proveedor agregado."); st.rerun()

with T2:
    if st.session_state.suppliers.empty: st.warning("Primero carga o registra proveedores.")
    else:
        opts=st.session_state.suppliers.apply(lambda r:f"{r.get('ruc','')} | {r.get('razon','')}",axis=1).tolist(); sel=st.selectbox("Proveedor",opts,key='sel_ind'); idx=opts.index(sel); s=st.session_state.suppliers.iloc[idx].to_dict(); key=supplier_key(s)
        st.markdown(f"<div class='card'><div class='big'>{ptxt(s.get('razon'))}</div>RUC {ptxt(s.get('ruc'))} · Estado: <b>{ptxt(s.get('estado'))}</b></div>",unsafe_allow_html=True)
        with st.form('edit_supplier'):
            cols=st.columns(3); vals={}
            fields=[('razon','Razón social'),('ruc','RUC'),('nombre_comercial','Nombre comercial'),('tipo','Persona'),('representante','Representante legal'),('contacto','Contacto'),('telefono','Teléfono'),('email','Correo'),('direccion','Dirección legal'),('ubicacion_fisica','Ubicación física'),('web','Página web'),('servicio','Actividad con CENASE'),('actividad_ruc','Actividad principal RUC'),('inicio_operaciones','Inicio operaciones'),('inicio_servicio','Inicio servicio CENASE'),('responsable_cenase','Responsable CENASE')]
            for i,(k,l) in enumerate(fields):
                if k=='tipo': vals[k]=cols[i%3].selectbox(l,["Jurídica","Natural"],index=0 if s.get(k,'Jurídica')!='Natural' else 1,key=f'e_{k}')
                else: vals[k]=cols[i%3].text_input(l,value=str(s.get(k,'')),key=f'e_{k}')
            vals['estado']=st.selectbox("Estado del proveedor",SUPPLIER_STATUS,index=SUPPLIER_STATUS.index(s.get('estado')) if s.get('estado') in SUPPLIER_STATUS else 0)
            vals['beneficiarios']=st.text_area("Beneficiarios finales / estructura relevante",value=str(s.get('beneficiarios','')))
            vals['notas']=st.text_area("Notas internas",value=str(s.get('notas','')))
            if st.form_submit_button("Guardar cambios",type='primary'):
                for k,v in vals.items(): st.session_state.suppliers.at[idx,k]=clean_ruc(v) if k=='ruc' else v
                st.success("Datos actualizados."); st.rerun()
        miss=missing_fields(st.session_state.suppliers.iloc[idx].to_dict())
        if miss: st.warning("Falta completar: "+", ".join(miss))
        else: st.success("Datos mínimos completos.")
        st.subheader("📎 Evidencias / documentos del proveedor")
        uploads=st.file_uploader("Adjuntar PDF, imagen, Excel u otro soporte",accept_multiple_files=True,key=f'files_{key}')
        if uploads and st.button("Guardar archivos adjuntos",key=f'save_files_{key}'):
            current=st.session_state.evidence.setdefault(key,[]); existing={(x['name'],x.get('sha256')) for x in current}
            added=0
            for f in uploads:
                raw=f.getvalue(); item={'name':f.name,'bytes':raw,'sha256':sha256_bytes(raw),'uploaded_at':datetime.now().isoformat()}
                if (item['name'],item['sha256']) not in existing: current.append(item); added+=1
            st.success(f"{added} archivo(s) agregado(s).")
        ev=st.session_state.evidence.get(key,[])
        if ev:
            st.dataframe(pd.DataFrame([{k:v for k,v in x.items() if k!='bytes'} for x in ev]),use_container_width=True,hide_index=True)

with T3:
    if st.session_state.suppliers.empty: st.warning("Primero carga proveedores.")
    else:
        opts=st.session_state.suppliers.apply(lambda r:f"{r.get('ruc','')} | {r.get('razon','')}",axis=1).tolist(); sel=st.selectbox("Proveedor a verificar",opts,key='sel_verify'); idx=opts.index(sel); s=st.session_state.suppliers.iloc[idx].to_dict(); key=supplier_key(s); current=st.session_state.assess.get(key,{})
        st.subheader("1. Criticidad")
        flags={}; cols=st.columns(2)
        for i,(rk,q,w) in enumerate(RISK_QUESTIONS): flags[rk]=cols[i%2].checkbox(f"{q} ({w} pts)",value=bool(current.get(rk,False)),key=f'risk_{rk}_{key}')
        label,score=calc_risk(flags); c1,c2,c3=st.columns(3); c1.metric("Criticidad",label); c2.metric("Puntaje",f"{score}/100"); c3.metric("Reevaluación sugerida",str(due_date_by_risk(label)))
        a,b=st.columns(2); basc_opts=["PENDIENTE","Sí","No","NO APLICA"]; contract_opts=["PENDIENTE","Sí","No"]; old_basc=current.get('has_basc','PENDIENTE'); old_contract=current.get('has_contract','PENDIENTE'); has_basc=a.selectbox("¿Cuenta con certificado BASC?",basc_opts,index=basc_opts.index(old_basc) if old_basc in basc_opts else 0,key=f'basc_{key}'); has_contract=b.selectbox("¿Tiene contrato/acuerdo de confidencialidad con CENASE?",contract_opts,index=contract_opts.index(old_contract) if old_contract in contract_opts else 0,key=f'contract_{key}')
        c1,c2=st.columns(2); croquis=c1.file_uploader("Croquis / mapa de ubicación (imagen)",type=['png','jpg','jpeg'],key=f'croquis_{key}'); foto=c2.file_uploader("Fotografía de ubicación (imagen)",type=['png','jpg','jpeg'],key=f'foto_{key}')
        st.subheader("2. Verificaciones")
        verifs={}
        for i,v in enumerate(VERIFICATIONS):
            old=current.get('verifs',{}).get(v,{})
            c1,c2,c3=st.columns([2.3,1.3,3.2]); res=c1.selectbox(v,RESULTS,index=RESULTS.index(old.get('resultado')) if old.get('resultado') in RESULTS else 0,key=f'v_{i}_{key}'); fec=c2.date_input("Fecha",value=TODAY,key=f'd_{i}_{key}',label_visibility='collapsed'); ev=c3.text_input("Evidencia / referencia / hallazgo",value=str(old.get('evidencia','')),key=f've_{i}_{key}',placeholder="Ej.: PDF SRI, captura, URL, número de proceso")
            verifs[v]={'resultado':res,'fecha':fec.isoformat(),'evidencia':ev}
        st.subheader("3. Evaluación de cumplimiento")
        evaluation={}; cols=st.columns(3); eval_opts=["PENDIENTE","CONFORME","PARCIAL","NO CONFORME","NO APLICA"]
        for i,(crit,w) in enumerate(EVAL_WEIGHTS.items()):
            old=current.get('evaluation',{}).get(crit,'PENDIENTE'); evaluation[crit]=cols[i%3].selectbox(f"{crit} ({w} pts)",eval_opts,index=eval_opts.index(old) if old in eval_opts else 0,key=f'ev_{i}_{key}')
        total,den,epct=calc_eval(evaluation); st.progress(min(epct/100,1.0),text=f"Evaluación: {epct:.1f}% ({total:.1f}/{den:.1f})")
        st.subheader("4. Checklist BASC")
        checklist={}; chk_opts=["PENDIENTE","CONFORME","NO CONFORME","N/A"]
        with st.expander("Completar 40 controles",expanded=False):
            for i,(cat,control) in enumerate(CHECKS,1):
                old=current.get('checklist',{}).get(str(i),'PENDIENTE'); checklist[str(i)]=st.selectbox(f"{i}. [{cat}] {control}",chk_opts,index=chk_opts.index(old) if old in chk_opts else 0,key=f'chk_{i}_{key}')
        st.write(f"Cumplimiento checklist: **{checklist_pct(checklist):.1f}%**")
        st.subheader("5. Responsables y decisión")
        a,b,c=st.columns(3); verified_by=a.text_input("Verificado por",value=current.get('verified_by',s.get('responsable_cenase',''))); verified_date=b.date_input("Fecha evaluación",value=TODAY); approved_by=c.text_input("Aprobado por",value=current.get('approved_by',''))
        temp={**flags,'risk':{'label':label,'score':score,'next':due_date_by_risk(label).isoformat()},'verifs':verifs,'evaluation':evaluation,'checklist':checklist,'has_basc':has_basc,'has_contract':has_contract}
        suggestion=suggested_decision(s,temp); st.info(f"Decisión sugerida por reglas de control: **{suggestion}**")
        decision=st.selectbox("Decisión final",DECISIONS,index=DECISIONS.index(current.get('decision')) if current.get('decision') in DECISIONS else 0)
        approval_date=st.date_input("Fecha de aprobación / decisión",value=TODAY)
        if st.button("💾 Guardar evaluación y crear histórico",type='primary'):
            ass={**flags,'risk':{'label':label,'score':score,'next':due_date_by_risk(label).isoformat()},'verifs':verifs,'evaluation':evaluation,'checklist':checklist,'has_basc':has_basc,'has_contract':has_contract,
                 'verified_by':verified_by,'verified_date':verified_date.isoformat(),'approved_by':approved_by,'approval_date':approval_date.isoformat(),'decision':decision,
                 'croquis_bytes':croquis.getvalue() if croquis else current.get('croquis_bytes'), 'foto_bytes':foto.getvalue() if foto else current.get('foto_bytes')}
            st.session_state.assess[key]=ass
            hist=jsonable({k:v for k,v in ass.items() if k not in ['croquis_bytes','foto_bytes']}); hist['saved_at']=datetime.now().isoformat(); st.session_state.history.setdefault(key,[]).append(hist)
            # Sincroniza estado del proveedor con la decisión.
            mapstate={'APROBADO':'APROBADO','APROBADO CONDICIONADO':'APROBADO CONDICIONADO','NO APROBADO / BLOQUEADO':'BLOQUEADO','PENDIENTE':'EN VERIFICACIÓN'}
            st.session_state.suppliers.at[idx,'estado']=mapstate.get(decision,'EN VERIFICACIÓN')
            st.success("Evaluación guardada y registrada en el histórico."); st.rerun()
        ass=st.session_state.assess.get(key,temp)
        st.divider(); st.subheader("📄 Documentos individuales")
        evidence=st.session_state.evidence.get(key,[]); cols=st.columns(3)
        docs=[('conf','Acuerdo confidencialidad','01_Acuerdo_Confidencialidad.pdf'),('seguridad','Acuerdo seguridad BASC','02_Acuerdo_Seguridad_BASC.pdf'),('verificacion','Registro verificación','03_Registro_Verificacion.pdf'),('evaluacion','Evaluación criticidad','04_Evaluacion_Criticidad.pdf'),('plan','Plan de acción','05_Plan_Accion.pdf'),('expediente','Expediente completo','06_Expediente_BASC_Completo.pdf')]
        for i,(kind,labelbtn,nm) in enumerate(docs): cols[i%3].download_button(labelbtn,build_pdf(s,kind,ass,evidence),f"{clean_ruc(s.get('ruc'))}_{nm}","application/pdf",key=f'dl_{kind}_{key}')
        st.download_button("📦 Descargar expediente completo ZIP",supplier_package(s,ass,key),f"{clean_ruc(s.get('ruc'))}_{safe_filename(s.get('razon'))}_EXPEDIENTE_BASC.zip","application/zip")

with T4:
    if st.session_state.suppliers.empty: st.warning("Primero carga proveedores.")
    else:
        opts=st.session_state.suppliers.apply(lambda r:f"{r.get('ruc','')} | {r.get('razon','')}",axis=1).tolist(); sel=st.selectbox("Proveedor",opts,key='sel_actions'); idx=opts.index(sel); s=st.session_state.suppliers.iloc[idx].to_dict(); key=supplier_key(s)
        st.subheader("🧯 Plan de acción / no conformidades")
        with st.form(f'action_{key}'):
            hall=st.text_area("Hallazgo / acción requerida"); a,b,c=st.columns(3); resp=a.text_input("Responsable"); fcomp=b.date_input("Fecha compromiso",value=TODAY+timedelta(days=30)); estado=c.selectbox("Estado",["ABIERTO","EN PROCESO","CERRADO"])
            cierre=st.text_area("Evidencia / comentario de cierre")
            if st.form_submit_button("Agregar acción",type='primary'):
                st.session_state.actions.setdefault(key,[]).append({'hallazgo':hall,'responsable':resp,'fecha_compromiso':fcomp.isoformat(),'estado':estado,'fecha_cierre':TODAY.isoformat() if estado=='CERRADO' else '', 'cierre':cierre,'created_at':datetime.now().isoformat()}); st.success("Acción registrada."); st.rerun()
        actions=st.session_state.actions.get(key,[])
        if actions: st.dataframe(pd.DataFrame(actions),use_container_width=True,hide_index=True)
        else: st.info("No hay acciones registradas.")
        st.subheader("🕘 Histórico de evaluaciones")
        hist=st.session_state.history.get(key,[])
        if hist:
            summary=[]
            for h in hist:
                total,den,pct=calc_eval(h.get('evaluation',{})); summary.append({'Guardado':h.get('saved_at'),'Fecha evaluación':h.get('verified_date'),'Criticidad':h.get('risk',{}).get('label'),'Riesgo':h.get('risk',{}).get('score'),'% evaluación':pct,'Decisión':h.get('decision'),'Verificado por':h.get('verified_by'),'Aprobado por':h.get('approved_by')})
            st.dataframe(pd.DataFrame(summary),use_container_width=True,hide_index=True)
        else: st.info("Aún no existen versiones históricas para este proveedor.")

with T5:
    st.subheader("📄 Generación masiva")
    st.write("Genera un ZIP con carpeta individual por proveedor, todos sus PDFs, evidencias adjuntas y ficha digital JSON. Los proveedores no evaluados quedan expresamente como PENDIENTES.")
    status_filter=st.multiselect("Estados a incluir",SUPPLIER_STATUS,default=SUPPLIER_STATUS)
    if st.button("Generar ZIP masivo",type='primary',disabled=st.session_state.suppliers.empty):
        zbuf=io.BytesIO(); included=[]
        with zipfile.ZipFile(zbuf,'w',zipfile.ZIP_DEFLATED) as z:
            for _,row in st.session_state.suppliers.iterrows():
                s=row.to_dict();
                if s.get('estado') not in status_filter: continue
                key=supplier_key(s); ass=st.session_state.assess.get(key,{})
                if 'risk' not in ass: ass={'risk':{'label':'PENDIENTE','score':0,'next':''},'verifs':{},'evaluation':{},'checklist':{},'decision':'PENDIENTE'}
                folder=f"{clean_ruc(s.get('ruc'))}_{safe_filename(s.get('razon'))}"; evidence=st.session_state.evidence.get(key,[])
                docs=[('conf','01_Acuerdo_Confidencialidad.pdf'),('seguridad','02_Acuerdo_Seguridad_BASC.pdf'),('verificacion','03_Registro_Verificacion.pdf'),('evaluacion','04_Evaluacion_Criticidad.pdf'),('plan','05_Plan_Accion.pdf'),('expediente','06_Expediente_BASC_Completo.pdf')]
                for kind,nm in docs: z.writestr(f"{folder}/{nm}",build_pdf(s,kind,ass,evidence))
                for e in evidence: z.writestr(f"{folder}/EVIDENCIAS/{safe_filename(e['name'])}",e['bytes'])
                z.writestr(f"{folder}/07_Ficha_Digital.json",json.dumps(jsonable({'proveedor':s,'evaluacion':{k:v for k,v in ass.items() if k not in ['croquis_bytes','foto_bytes']},'acciones':st.session_state.actions.get(key,[])}),ensure_ascii=False,indent=2))
                included.append(s.get('ruc'))
            rec=[r for r in report_rows() if r['RUC'] in included]
            z.writestr('00_REPORTE_MAESTRO_BASC.xlsx',make_report_excel(rec))
            z.writestr('00_LEEME.txt',"Expedientes BASC de proveedores CENASE. Los estados PENDIENTE indican verificaciones no concluidas; no deben interpretarse como conformidad.")
        zbuf.seek(0); st.session_state.bulk_zip=zbuf.getvalue(); st.success(f"ZIP generado para {len(included)} proveedor(es).")
    if st.session_state.get('bulk_zip'): st.download_button("⬇️ Descargar expedientes masivos",st.session_state.bulk_zip,f"CENASE_BASC_Proveedores_{TODAY}.zip","application/zip")

with T6:
    rows=report_rows(); rep=pd.DataFrame(rows)
    c1,c2,c3,c4,c5=st.columns(5)
    c1.metric('Total',len(rep)); c2.metric('Aprobados',int(rep['Decisión'].eq('APROBADO').sum()) if len(rep) else 0); c3.metric('Condicionados',int(rep['Decisión'].eq('APROBADO CONDICIONADO').sum()) if len(rep) else 0); c4.metric('Bloqueados',int(rep['Decisión'].eq('NO APROBADO / BLOQUEADO').sum()) if len(rep) else 0); c5.metric('Vencidos',int(rep['Vigencia'].eq('VENCIDO').sum()) if len(rep) else 0)
    if len(rep):
        st.dataframe(rep,use_container_width=True,hide_index=True)
        st.subheader("Prioridades")
        priority=rep[(rep['Vigencia'].isin(['VENCIDO','POR VENCER'])) | (rep['Alertas críticas']=='SÍ') | (rep['Acciones abiertas']>0)]
        if len(priority): st.dataframe(priority,use_container_width=True,hide_index=True)
        else: st.success("No hay vencimientos próximos, alertas críticas ni acciones abiertas registradas.")
    st.download_button("⬇️ Reporte maestro Excel",make_report_excel(rows),f"Reporte_Maestro_BASC_CENASE_{TODAY}.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.caption("El puntaje sirve como herramienta de gestión. La decisión final debe considerar hallazgos críticos, evidencia y aprobación del responsable autorizado.")
