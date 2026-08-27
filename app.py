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

APP_VERSION = "2.3"
TODAY = date.today()
BASE_DIR = Path(__file__).resolve().parent
LOGO_PATH = BASE_DIR / "assets" / "logo_cenase.png"
CENASE = {
    "razon": "CENTRO DE ASESORAMIENTO Y SEGURIDAD EMPRESARIAL CENASE CIA. LTDA.",
    "ruc": "0991317791001",
    "representante": "NELLI OLIMPIA GUAYGUA REYES",
    "cargo": "Gerente General",
    "direccion": "Cdla. Miraflores, Av. Guayas 303",
    "telefono": "044 608055",
    "correo": "bcamacho@cenase.ec; contador@cenase.ec",
    "web": "www.cenase.ec",
    "contacto": "Nathaly Varela",
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
    # Mantiene todos los campos de la plantilla masiva oficial de CENASE.
    return {
        "n_proveedor":"",
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
    # Mapeo explícito de TODOS los campos de "REPORTE PROVEEDORES CORRECTO 2026".
    aliases = {
        "n_proveedor":["n proveedor","n° proveedor","numero proveedor"],
        "ruc":["ruc","identificacion","cedula ruc","numero identificacion","documento"],
        "razon":["razon social","nombre razon social","persona","cliente proveedor","proveedor","nombre"],
        "nombre_comercial":["nombre comercial"],
        "tipo":["tipo persona","tipo","clase"],
        "representante":["representante legal","representante"],
        "contacto":["contacto","persona contacto"],
        "telefono":["telefono","telefonos","celular"],
        "email":["correo","email","e mail","correo electronico"],
        "direccion":["direccion","direccion principal","direccion legal"],
        "ubicacion_fisica":["ubicacion fisica","ubicación fisica","ubicación_fisica","ubicacion_fisica"],
        "web":["pagina web","web","sitio web"],
        "servicio":["producto servicio","producto / servicio","servicio","actividad comercial","concepto"],
        "actividad_ruc":["actividad principal","actividad economica","actividad ruc"],
        "inicio_operaciones":["inicio de operaciones","inicio operaciones"],
        "inicio_servicio":["inicio servicio","inicio servicio cenase","inicio de servicio"],
        "beneficiarios":["beneficiarios","beneficiarios finales","beneficiario final"],
        "estado":["estado","estado proveedor"],
        "responsable_cenase":["responsable cenase","responsable_cenase","responsable"],
        "notas":["notas","observaciones","nota"],
    }
    ncols={norm(c):c for c in columns}; out={}
    for target,als in aliases.items():
        for a in als:
            if norm(a) in ncols:
                out[target]=ncols[norm(a)]
                break
        if target not in out:
            for nc,orig in ncols.items():
                if any(norm(a) in nc or nc in norm(a) for a in als):
                    out[target]=orig
                    break
    return out

def load_suppliers(upload):
    name=upload.name.lower()
    if name.endswith('.csv'):
        upload.seek(0); df=pd.read_csv(upload,dtype=str,keep_default_na=False)
    else:
        upload.seek(0); xls=pd.ExcelFile(upload)
        best=None
        for sn in xls.sheet_names:
            tmp=pd.read_excel(xls,sheet_name=sn,dtype=str,keep_default_na=False)
            nc=[norm(c) for c in tmp.columns]
            header_bonus=100000 if ("ruc" in nc and "razon social" in nc) else 0
            score=header_bonus + tmp.shape[0]*max(tmp.shape[1],1)
            if best is None or score>best[0]: best=(score,tmp)
        df=best[1]
    cmap=column_map(df.columns)
    rows=[]
    for pos,(_,r) in enumerate(df.iterrows(),1):
        s=empty_supplier()
        for k,c in cmap.items():
            s[k]=str(r.get(c,'')).strip()
        s['ruc']=clean_ruc(s['ruc'])
        if not s['razon'] and not s['ruc']:
            continue
        if s['tipo']:
            s['tipo']='Natural' if 'natural' in norm(s['tipo']) else 'Jurídica'
        if not s.get('n_proveedor'):
            s['n_proveedor']=str(pos)
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
    # Logo institucional en TODAS las páginas PDF.
    try:
        if LOGO_PATH.exists():
            canvas.drawImage(str(LOGO_PATH),w-5.0*cm,h-1.35*cm,width=3.5*cm,height=0.80*cm,preserveAspectRatio=True,mask='auto')
    except Exception:
        pass
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

def contract_signature_table(s):
    proveedor_firma=s.get('representante') or 'REPRESENTANTE LEGAL PENDIENTE'
    return Table([
        [Paragraph("<b>CENASE</b>",CENTER),Paragraph("<b>PROVEEDOR / ASOCIADO DE NEGOCIO</b>",CENTER)],
        ["\n\n\n_______________________________","\n\n\n_______________________________"],
        [Paragraph("<b>NELLI OLIMPIA GUAYGUA REYES</b>",CENTER),Paragraph(f"<b>{ptxt(proveedor_firma)}</b>",CENTER)],
        [Paragraph("Gerente General<br/>CENTRO DE ASESORAMIENTO Y SEGURIDAD EMPRESARIAL CENASE CIA. LTDA.<br/>RUC 0991317791001",CENTER),Paragraph(f"Representante legal<br/>{ptxt(s.get('razon',''))}<br/>RUC {ptxt(s.get('ruc',''))}",CENTER)],
        [Paragraph("Fecha: __________________",CENTER),Paragraph("Fecha: __________________",CENTER)],
    ],colWidths=[8.1*cm,8.1*cm])

def signing_package_zip(s, ass=None, evidence_items=None):
    ass=ass or {}; evidence_items=evidence_items or []
    b=io.BytesIO()
    prefix=f"{clean_ruc(s.get('ruc'))}_{safe_filename(s.get('razon'))}"
    with zipfile.ZipFile(b,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{prefix}_00_Acuerdo_Completo_CENASE_Anexo_BASC.pdf",build_pdf(s,'acuerdo_completo',ass,evidence_items))
        z.writestr(f"{prefix}_01_Acuerdo_Confidencialidad_Proteccion_Datos.pdf",build_pdf(s,'conf',ass,evidence_items))
        z.writestr(f"{prefix}_02_Acuerdo_Seguridad_Asociado_BASC.pdf",build_pdf(s,'seguridad',ass,evidence_items))
        z.writestr("LEEME.txt","El archivo 00_Acuerdo_Completo reproduce en un solo PDF el acuerdo contractual y su Anexo BASC, preparado para firma de CENASE y del representante legal del proveedor. Verifique los datos antes de suscribirlo.")
    b.seek(0)
    return b.getvalue()

def build_pdf(s,kind="expediente",ass=None,evidence_items=None):
    ass=ass or {}; evidence_items=evidence_items or []
    risk=ass.get('risk') or {'label':'BAJA','score':0,'next':due_date_by_risk('BAJA')}
    checklist=ass.get('checklist',{}); verifs=ass.get('verifs',{}); evaluation=ass.get('evaluation',{})
    buf=io.BytesIO(); doc=SimpleDocTemplate(buf,pagesize=A4,rightMargin=1.35*cm,leftMargin=1.35*cm,topMargin=1.9*cm,bottomMargin=1.25*cm)
    titlemap={"conf":"ACUERDO DE CONFIDENCIALIDAD Y PROTECCIÓN DE DATOS PERSONALES","seguridad":"ACUERDO DE SEGURIDAD COMO ASOCIADO DE NEGOCIO BASC","acuerdo_completo":"ACUERDO DE PROVEEDOR CENASE + ANEXO BASC","verificacion":"REGISTRO DE VERIFICACIÓN DE ASOCIADOS DE NEGOCIO","evaluacion":"EVALUACIÓN Y CRITICIDAD DEL ASOCIADO DE NEGOCIO","plan":"PLAN DE ACCIÓN DEL ASOCIADO DE NEGOCIO","expediente":"EXPEDIENTE BASC COMPLETO DEL ASOCIADO DE NEGOCIO"}
    # Los acuerdos siguen el formato contractual original; los demás documentos usan ficha inicial.
    story=[] if kind in ("conf","seguridad","acuerdo_completo") else [Paragraph(titlemap[kind],TITLE),info_table(s),Spacer(1,7)]

    def conf_section():
        proveedor=s.get('razon') or 'PROVEEDOR PENDIENTE'
        ruc=s.get('ruc') or 'PENDIENTE'
        rep=s.get('representante') or 'REPRESENTANTE LEGAL PENDIENTE'
        domicilio=s.get('direccion') or 'PENDIENTE'
        telefono=s.get('telefono') or 'PENDIENTE'
        correo=s.get('email') or 'PENDIENTE'
        contacto=s.get('contacto') or rep
        nprov=s.get('n_proveedor') or '—'
        blue=colors.HexColor('#17365D')
        light=colors.HexColor('#D9EAF7')
        # Formato visual basado en el Excel original de CENASE: logo arriba, título negro sobre fondo blanco.
        if LOGO_PATH.exists():
            logo_doc = RLImage(str(LOGO_PATH), width=3.65*cm, height=0.88*cm)
            logo_tbl = Table([["", logo_doc]], colWidths=[12.2*cm,4.2*cm])
            logo_tbl.setStyle(TableStyle([('ALIGN',(1,0),(1,0),'CENTER'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('BOTTOMPADDING',(0,0),(-1,-1),2)]))
        else:
            logo_tbl = Spacer(1,1)
        title=Table([[Paragraph("<b>ACUERDO DE CONFIDENCIALIDAD Y PROTECCIÓN DE DATOS PERSONALES</b>",CENTER)]],colWidths=[16.4*cm])
        title.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.white),('TEXTCOLOR',(0,0),(-1,-1),colors.black),('LINEBELOW',(0,0),(-1,-1),0.45,colors.HexColor('#B7B7B7')),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4)]))
        provtbl=Table([
            [Paragraph("<b>PROVEEDOR</b>",CENTER),"",],
            [Paragraph("Dirección:",SMALL),Paragraph(ptxt(domicilio),SMALL)],
            [Paragraph("Teléfonos:",SMALL),Paragraph(ptxt(telefono),SMALL)],
            [Paragraph("Correo electrónico:",SMALL),Paragraph(ptxt(correo),SMALL)],
            [Paragraph("Persona de contacto:",SMALL),Paragraph(ptxt(contacto),SMALL)],
        ],colWidths=[5.8*cm,10.6*cm])
        provtbl.setStyle(TableStyle([('SPAN',(0,0),(1,0)),('BACKGROUND',(0,0),(1,0),light),('ALIGN',(0,0),(1,0),'CENTER'),('GRID',(0,0),(-1,-1),0.5,colors.HexColor('#666666')),('VALIGN',(0,0),(-1,-1),'TOP')]))
        centbl=Table([
            [Paragraph("<b>CENASE</b>",CENTER),""],
            [Paragraph("Dirección:",SMALL),Paragraph(ptxt(CENASE['direccion']),SMALL)],
            [Paragraph("Teléfonos:",SMALL),Paragraph(ptxt(CENASE['telefono']),SMALL)],
            [Paragraph("Correo electrónico:",SMALL),Paragraph(ptxt(CENASE['correo']),SMALL)],
            [Paragraph("Persona de contacto:",SMALL),Paragraph(ptxt(CENASE['contacto']),SMALL)],
        ],colWidths=[5.8*cm,10.6*cm])
        centbl.setStyle(TableStyle([('SPAN',(0,0),(1,0)),('BACKGROUND',(0,0),(1,0),light),('ALIGN',(0,0),(1,0),'CENTER'),('GRID',(0,0),(-1,-1),0.5,colors.HexColor('#666666')),('VALIGN',(0,0),(-1,-1),'TOP')]))
        return [
            logo_tbl, Spacer(1,4), title, Spacer(1,6),
            Paragraph(f"<b>N° PROVEEDOR:</b> {ptxt(nprov)}",BODY),
            Paragraph("Conste por el presente documento el Acuerdo de Confidencialidad y Protección de Datos, que celebran de una parte:",BODY),
            Paragraph(f"<b>A.</b> La compañía de seguridad {CENASE['razon']}, con RUC {CENASE['ruc']}, debida y legalmente representada por {CENASE['representante']} – {CENASE['cargo']}, cuya personería se acredita con el nombramiento que se adjunta al presente instrumento en calidad de documento habilitante, a quien en lo posterior se la denominará “CENASE”, por otra parte;",BODY),
            Paragraph(f"<b>B.</b> La compañía {ptxt(proveedor)}, con RUC {ptxt(ruc)}, debida y legalmente representada por {ptxt(rep)}, cuya personería se acredita con el nombramiento que se adjunta al presente instrumento en calidad de documento habilitante, parte a la que para los efectos del presente contrato se la denominará en lo sucesivo como “EL PROVEEDOR”.",BODY),
            Paragraph("<b>PRIMERA: OBJETO.-</b> El presente Acuerdo tiene por objeto garantizar el secreto, confidencialidad y el uso lícito de toda la información y los datos personales a los que el PROVEEDOR tenga acceso, directa o indirectamente, con ocasión de los productos entregados o servicios prestados a CENASE (cadena de suministro, soporte técnico, sistemas, equipos de seguridad, asesorías, entre otros).",BODY),
            Paragraph("<b>SEGUNDA: CONFIDENCIALIDAD DE LA INFORMACIÓN.-</b> El PROVEEDOR reconoce que toda la información comercial, técnica, financiera, listados de clientes, planes de seguridad, vulnerabilidades, claves de acceso o estrategias de CENASE es de propiedad exclusiva de esta última y tiene carácter de estrictamente confidencial. En consecuencia, el PROVEEDOR se obliga a:",BODY),
            Paragraph("1. Utilizar la información única y exclusivamente para cumplir con la provisión solicitada.",BODY),
            Paragraph("2. No divulgar, copiar, reproducir ni transferir dicha información a ningún tercero sin la autorización previa y por escrito de CENASE.",BODY),
            Paragraph("3. Mantener el secreto profesional incluso después de terminada la relación de provisión, de forma indefinida.",BODY),
            Paragraph("<b>TERCERA: PROTECCIÓN DE DATOS PERSONALES.-</b> En cumplimiento de la Ley Orgánica de Protección de Datos Personales (LOPDP), las partes declaran que CENASE actúa como Responsable del Tratamiento y el PROVEEDOR actuará en calidad de Encargado del Tratamiento si para la ejecución de su labor requiere acceder a bases de datos, imágenes de videovigilancia, registros de personal o clientes de CENASE. Por lo tanto, el PROVEEDOR se compromete a:",BODY),
            Paragraph("1. Tratar los datos personales únicamente bajo las instrucciones de CENASE y para los fines propios del servicio/producto.",BODY),
            Paragraph("2. Implementar medidas de seguridad básicas (técnicas y organizativas) para evitar la pérdida, robo o acceso no autorizado a los datos.",BODY),
            Paragraph("3. Notificar a CENASE de manera inmediata (máximo en 24 horas) cualquier sospecha de incidente o brecha de seguridad.",BODY),
            Paragraph("4. Eliminar o devolver todos los datos personales a los que tuvo acceso una vez concluida la entrega del bien o servicio, salvo obligación legal de conservación.",BODY),
            Paragraph("<b>CUARTA: RESPONSABILIDAD.-</b> El PROVEEDOR asume la responsabilidad total por cualquier filtración de información o mal uso de datos personales atribuible a su personal o técnicos externos. En caso de que CENASE reciba sanciones, multas o demandas bajo la Ley Orgánica de Protección de Datos Personales (LOPDP) por negligencia del PROVEEDOR, este último estará obligado a indemnizar y reembolsar a CENASE la totalidad de los valores económicos afectados.",BODY),
            Paragraph("<b>QUINTA: DOMICILIO, DIRECCIÓN Y COMUNICACIONES.-</b> LAS PARTES señalan que cualquier notificación requerida por el presente documento se hará por escrito y se considerará suficiente cuando sea enviada por correo electrónico en las siguientes direcciones:",BODY),
            provtbl, Spacer(1,7), centbl, Spacer(1,5),
            Paragraph("Las partes deberán notificar a las otras en caso de que exista un cambio en el lugar donde se deben realizar las notificaciones; si no se notificare, se entenderán correctamente realizadas en las direcciones antes detalladas.",BODY),
            Paragraph(f"<font color='#5B9BD5'>{CENASE['web']}</font>",BODY),
            Paragraph("<b>VIGÉSIMA QUINTA: Son Documentos anexos a este contrato:</b>",BODY),
            Paragraph("• Acuerdo de seguridad como asociado de negocio BASC<br/>• Copia de Registro Único de Contribuyente vigente de CENASE<br/>• Copia de Registro Único de Contribuyente vigente del PROVEEDOR<br/>• Copia de cédula del Rep. Legal de CENASE<br/>• Copia de cédula del Rep. Legal del PROVEEDOR<br/>• Cotización de servicios aprobados",BODY),
            Paragraph("<b>QUINTA: ACEPTACIÓN Y FIRMA.-</b> Libre y voluntariamente, previo el cumplimiento de todos los requisitos exigidos por las leyes de la materia, las partes declaran expresamente su aceptación a todo lo convenido en el presente contrato, a cuyas estipulaciones se someten.",BODY),
            Paragraph("Las Partes acuerdan que el presente contrato podrá ser suscrito de forma manuscrita o mediante firma electrónica. De conformidad con los artículos 14, 45 y 46 de la Ley de Comercio Electrónico, Firmas Electrónicas y Mensajes de Datos, la firma electrónica tiene igual validez y los mismos efectos jurídicos que la firma manuscrita, por lo que las Partes reconocen que el contrato suscrito por este medio es plenamente válido, vinculante y exigible. La firma electrónica deberá haber sido emitida por una entidad de certificación acreditada ante la ARCOTEL y podrá estamparse y verificarse a través de la herramienta oficial FirmaEC.",BODY),
            Paragraph(f"Para constancia de lo acordado, las partes intervinientes suscriben el presente contrato por triplicado en la ciudad de Guayaquil, el {TODAY.strftime('%d/%m/%Y')}.",BODY),
            Spacer(1,12),contract_signature_table(s)
        ]

    def security_section():
        blue=colors.HexColor('#3636A8')
        def bar(text):
            t=Table([[Paragraph(f"<b>{text}</b>",CENTER)]],colWidths=[16.4*cm])
            t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),blue),('TEXTCOLOR',(0,0),(-1,-1),colors.white),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4)]))
            return t
        security_logo = RLImage(str(LOGO_PATH), width=3.65*cm, height=0.88*cm) if LOGO_PATH.exists() else Spacer(1,1)
        return [
            Table([["", security_logo]], colWidths=[12.2*cm,4.2*cm], style=[('ALIGN',(1,0),(1,0),'CENTER')]),
            Spacer(1,4),
            Paragraph("<b>ANEXO</b>",CENTER),
            Paragraph("<font color='#005B9E'><b>ACUERDO DE SEGURIDAD DE ASOCIADOS DE NEGOCIO BASC</b></font>",CENTER),
            Spacer(1,10),
            Paragraph("En el lugar y fecha en que se suscribe el contrato principal, se celebran también los siguientes acuerdos de seguridad, el mismo que tiene estatus de documento formal y/o informativo, en el que se establecen relevantes aspectos de control y seguridad, con la finalidad de que la relación comercial entre CENASE y EL PROVEEDOR, que en adelante se lo llamará NUESTRO ASOCIADO DE NEGOCIO, se desarrolle respetando parámetros mínimos de seguridad establecidos en el SGCS BASC, sistema de gestión en control y seguridad implementado por CENASE para el cumplimiento de sus políticas.",BODY),
            Paragraph("A continuación, informamos nuestras políticas:",BODY),
            bar("POLÍTICA DE CONTROL Y SEGURIDAD"),
            Paragraph("<font color='#008FD5'><i>En CENASE, nos comprometemos a entregar el servicio de vigilancia y seguridad física cumpliendo el marco legal, promoviendo activamente una cultura de seguridad en nuestros procesos que nos lleven a la mejora continua, de manera que nuestro cliente se sienta seguro.</i></font>",BODY),
            Paragraph("<font color='#008FD5'><i>Por tal razón, CENASE cuenta con un Sistema de Gestión de Control y Seguridad basado en la norma y estándares BASC que constituye un apoyo fundamental para prevenir riesgos de actividades ilícitas, corrupción y soborno.</i></font>",BODY),
            bar("POLÍTICA DE RESPONSABILIDAD SOCIAL, ANTICORRUPCIÓN Y ANTISOBORNO"),
            Paragraph("<font color='#008FD5'><i>En CENASE respetamos los derechos humanos universales y la preservación de los recursos naturales, colaboramos con toda actividad relacionada con la prevención del abuso laboral, discriminación, abuso infantil, trabajo forzoso y abuso de los recursos medioambientales, cumpliendo todas las normativas relacionadas, socializando los aspectos relevantes e implementando una cultura de mejoramiento para las nuevas generaciones.</i></font>",BODY),
            Paragraph("<font color='#008FD5'><i>Denunciaremos toda actividad ilegal y deshonesta relacionada con corrupción y/o soborno en las actividades corporativas, no toleramos comportamientos ilegítimos y antijurídicos y nos comprometemos a implementar todas las acciones requeridas.</i></font>",BODY),
            Paragraph("<b>ACUERDOS GENERALES</b>",CENTER),
            Paragraph("<b>NUESTRO ASOCIADO DE NEGOCIO, se compromete a cumplir los siguientes aspectos críticos de seguridad, contenidos en los acuerdos generales o específicos del presente documento.</b>",BODY),
            Paragraph("• Se compromete a cumplir con la reglamentación y los requisitos legales aplicables a su giro de negocio.<br/>"
                      "• Declara que sus direcciones principales y sucursales son las que constan en la información registrada en los organismos de control; cualquier cambio de dirección principal o sucursal deberá ser notificado de manera inmediata al líder del proceso relacionado o al funcionario responsable de la gestión de asociados de negocio, prevención del lavado de activos y financiamiento del terrorismo de CENASE.<br/>"
                      "• Se compromete a guardar la confidencialidad de la información relacionada a su modelo operativo y el de CENASE.<br/>"
                      "• Declara no haber participado de manera personal y directa, ni en representación de su empresa, y/o prestando su nombre en representación de otra persona natural o jurídica, para el cometimiento o facilitación de actividades relacionadas con el lavado de activos, financiamiento del terrorismo o de otras actividades consideradas ilegales e ilícitas por los organismos de control gubernamental.<br/>"
                      "• Declara que los beneficiarios finales destinatarios de los recursos o bienes resultantes del contrato / prestación del servicio a CENASE son los registrados y autorizados por los entes de control; de igual manera declara que los recursos con los que cuenta de manera personal y/o empresarial para la prestación del servicio y el desarrollo de sus actividades comerciales tienen un origen y destino legal y lícito.<br/>"
                      "• Declara que sus representantes y accionistas no son Personas Expuestas Políticamente (PEP).<br/>"
                      "• CENASE se reserva el derecho a facilitar los datos de NUESTRO ASOCIADO DE NEGOCIO a las autoridades de control competentes, en cualquier momento y en cualquiera de las etapas de la actividad comercial, con la finalidad de asegurar la integridad de los procesos críticos y la información sensible.",BODY),
            Paragraph("<b>Importante:</b> El presente acuerdo de seguridad puede complementarse con otras directrices o instrucciones permanentes / temporales de seguridad que establezcan los involucrados, medidas tendientes a gestionar los riesgos de la operación / actividad u objeto de la relación comercial.",BODY),
            Paragraph(f"<font color='#5B9BD5'>{CENASE['web']}</font>",BODY),
            Spacer(1,12),contract_signature_table(s)
        ]

    def verification_section():
        light=colors.HexColor('#D9EAF7'); blue=colors.HexColor('#0070C0'); border=colors.HexColor('#666666')
        def P(v,style=SMALL): return Paragraph(ptxt(v or ''),style)
        def lab(n,t): return Paragraph(f"<font color='#0070C0'><b>{n}</b></font> &nbsp; <b>{ptxt(t)}</b>",SMALL)
        # Encabezado como el registro original.
        logo = RLImage(str(LOGO_PATH),width=3.4*cm,height=0.82*cm) if LOGO_PATH.exists() else Spacer(1,1)
        head=Table([[logo,Paragraph("<font color='#0070C0'><b>REGISTRO DE VERIFICACIÓN DE ASOCIADOS DE NEGOCIO</b></font>",ParagraphStyle('vrtitle',parent=CENTER,fontSize=14,leading=17))]],colWidths=[4.0*cm,12.4*cm])
        head.setStyle(TableStyle([('BACKGROUND',(1,0),(1,0),light),('BOX',(0,0),(-1,-1),0.7,border),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('ALIGN',(0,0),(0,0),'CENTER'),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8)]))
        info=[
          [lab(1,'Razón social:'),P(s.get('razon')),lab(2,'Nombre comercial:'),P(s.get('nombre_comercial')),lab(3,'Persona'),P(s.get('tipo'))],
          [lab(4,'Dirección declarada en los documentos legales:'),P(s.get('direccion')),lab(5,'Página WEB:'),P(s.get('web')),lab(6,'Teléfono:'),P(s.get('telefono'))],
          [lab(7,'Dirección de la ubicación física:'),P(s.get('ubicacion_fisica')),lab(8,'No. RUC:'),P(s.get('ruc')),lab(9,'Inicio operaciones:'),P(s.get('inicio_operaciones'))],
          [lab(10,'Actividad principal registrada en el RUC:'),P(s.get('actividad_ruc')),lab(11,'Nombre de contacto:'),P(s.get('contacto')),'',''],
          [lab(12,'Nombre del representante legal:'),P(s.get('representante')),lab(13,'Telf / E-mail:'),P((s.get('telefono') or '')+' / '+(s.get('email') or '')),'',''],
          [lab(14,'Fecha de inicio del servicio con CENASE:'),P(s.get('inicio_servicio')),lab(15,'Actividad comercial con CENASE:'),P(s.get('servicio')),lab(16,'Tipo de Asociado'),P('Proveedor')],
          [lab(17,'Beneficiarios finales'),P(s.get('beneficiarios')),'','','',''],
        ]
        it=Table(info,colWidths=[3.35*cm,4.25*cm,2.65*cm,3.25*cm,1.6*cm,1.3*cm])
        it.setStyle(TableStyle([('GRID',(0,0),(-1,-1),0.55,border),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),3),('RIGHTPADDING',(0,0),(-1,-1),3),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
        media_header=Table([[P('<b>17. CROQUIS (Ubicación física)</b>',CENTER),P('<b>18. FOTOGRAFÍA (Ubicación física)</b>',CENTER)]],colWidths=[8.1*cm,8.1*cm])
        media_header.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),light),('TEXTCOLOR',(0,0),(-1,-1),blue),('GRID',(0,0),(-1,-1),0.55,border)]))
        media=Table([[image_flowable(ass.get('croquis_bytes'),7.7*cm,6.1*cm),image_flowable(ass.get('foto_bytes'),7.7*cm,6.1*cm)]],colWidths=[8.1*cm,8.1*cm],rowHeights=[6.45*cm])
        media.setStyle(TableStyle([('GRID',(0,0),(-1,-1),0.55,border),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('ALIGN',(0,0),(-1,-1),'CENTER')]))
        v=verifs
        q=[
          ('19','¿La empresa cuenta con certificado BASC?',ass.get('has_basc','PENDIENTE')),
          ('20','¿El asociado tiene acceso a las instalaciones de la empresa?','Sí' if ass.get('access') else 'No'),
          ('21','¿El asociado tiene acceso a información confidencial de la empresa?','Sí' if ass.get('info') else 'No'),
          ('22','¿El asociado tiene suscrito contrato mercantil o acuerdo de confidencialidad con CENASE?',ass.get('has_contract','PENDIENTE')),
          ('23','¿Se constató el estado tributario de la empresa en el SRI?',v.get('RUC / estado tributario SRI',{}).get('resultado','PENDIENTE')),
          ('24','¿Se consultó la información de representantes legales / administradores / accionistas / beneficiarios finales en Supercias?',v.get('Superintendencia de Compañías',{}).get('resultado','PENDIENTE')),
          ('25','¿Se verificaron posibles demandas y juicios en la Función Judicial?',v.get('Función Judicial - proveedor',{}).get('resultado','PENDIENTE')),
          ('26','¿Se verificaron posibles demandas / noticias del delito en Fiscalía?',v.get('Fiscalía / fuentes oficiales - proveedor',{}).get('resultado','PENDIENTE')),
        ]
        qrows=[]
        for i in range(0,8,2):
            a,b=q[i],q[i+1]
            qrows.append([lab(a[0],a[1]),P(a[2],CENTER),lab(b[0],b[1]),P(b[2],CENTER)])
        qt=Table(qrows,colWidths=[6.8*cm,1.25*cm,6.8*cm,1.25*cm])
        qt.setStyle(TableStyle([('GRID',(0,0),(-1,-1),0.55,border),('BACKGROUND',(1,0),(1,-1),light),('BACKGROUND',(3,0),(3,-1),light),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
        res_head=Table([[Paragraph("<font color='#0070C0'><b>RESULTADO DE LA EVALUACIÓN: NIVEL DE CRITICIDAD</b></font>",CENTER),P('<b>fecha de evaluación</b>',CENTER)]],colWidths=[13.4*cm,2.8*cm])
        res_head.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),light),('GRID',(0,0),(-1,-1),0.55,border)]))
        fecha=ass.get('verified_date','PENDIENTE')
        desc=Table([[P(f"De acuerdo al análisis de la información suministrada, el potencial ASOCIADO DE NEGOCIO tiene el siguiente nivel de criticidad: <b>{risk.get('label','PENDIENTE')}</b>. Puntaje: {risk.get('score',0)}/100."),Paragraph(f"<font color='#C00000'><b>{ptxt(fecha)}</b></font>",ParagraphStyle('datecrit',parent=CENTER,fontSize=13))]],colWidths=[13.4*cm,2.8*cm])
        desc.setStyle(TableStyle([('GRID',(0,0),(-1,-1),0.55,border),('VALIGN',(0,0),(-1,-1),'MIDDLE')]))
        label=risk.get('label','PENDIENTE')
        boxes=Table([[P('<b>ALTO</b>',CENTER),P('X' if label in ('ALTA','CRÍTICA') else '',CENTER),P('<b>MEDIO</b>',CENTER),P('X' if label=='MEDIA' else '',CENTER),P('<b>BAJO</b>',CENTER),P('X' if label=='BAJA' else '',CENTER)]],colWidths=[2.8*cm,1.4*cm,2.8*cm,1.4*cm,2.8*cm,1.4*cm])
        boxes.setStyle(TableStyle([('BACKGROUND',(0,0),(0,0),colors.HexColor('#F4CCCC')),('BACKGROUND',(2,0),(2,0),colors.HexColor('#FFF2CC')),('BACKGROUND',(4,0),(4,0),colors.HexColor('#D9EAD3')),('GRID',(0,0),(-1,-1),0.5,border),('FONTSIZE',(0,0),(-1,-1),12),('ALIGN',(0,0),(-1,-1),'CENTER'),('VALIGN',(0,0),(-1,-1),'MIDDLE')]))
        foot=Table([[Paragraph("Este registro es realizado por el departamento de compras para el caso de proveedores, y el departamento comercial para el caso de clientes.<br/>Para llenar este formulario, se debe tomar los lineamientos del procedimiento de GESTIÓN DE ASOCIADOS DE NEGOCIO.",CENTER)]],colWidths=[16.2*cm])
        foot.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),light),('TEXTCOLOR',(0,0),(-1,-1),blue),('GRID',(0,0),(-1,-1),0.5,border)]))
        return [head,Spacer(1,4),it,Spacer(1,5),media_header,media,Spacer(1,6),qt,Spacer(1,6),res_head,desc,Spacer(1,6),boxes,Spacer(1,7),foot]

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
    elif kind=="acuerdo_completo": story+=conf_section()+[PageBreak()]+security_section()
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
            'N° Proveedor':s.get('n_proveedor'),'RUC':s.get('ruc'),'Razón social':s.get('razon'),
            'Nombre comercial':s.get('nombre_comercial'),'Tipo':s.get('tipo'),'Representante legal':s.get('representante'),
            'Contacto':s.get('contacto'),'Teléfono':s.get('telefono'),'Correo':s.get('email'),
            'Dirección':s.get('direccion'),'Ubicación física':s.get('ubicacion_fisica'),'Web':s.get('web'),
            'Producto / Servicio':s.get('servicio'),'Actividad principal RUC':s.get('actividad_ruc'),
            'Inicio de operaciones':s.get('inicio_operaciones'),'Inicio servicio':s.get('inicio_servicio'),
            'Beneficiarios':s.get('beneficiarios'),'Estado proveedor':s.get('estado'),
            'Responsable CENASE':s.get('responsable_cenase'),'Notas':s.get('notas'),
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
        df.to_excel(writer,index=False,sheet_name='Maestro BASC',startrow=4)
        wb=writer.book; ws=writer.sheets['Maestro BASC']
        titlefmt=wb.add_format({'bold':True,'font_color':'#17365D','font_size':16})
        ws.write('C1','CENASE - REPORTE MAESTRO BASC DE ASOCIADOS DE NEGOCIO',titlefmt)
        if LOGO_PATH.exists():
            try: ws.insert_image('A1',str(LOGO_PATH),{'x_scale':0.65,'y_scale':0.65})
            except Exception: pass
        head=wb.add_format({'bold':True,'font_color':'white','bg_color':'#4472C4','border':1,'align':'center','valign':'vcenter','text_wrap':True})
        pct=wb.add_format({'num_format':'0.0','align':'center'})
        header_row=4
        for c,col in enumerate(df.columns):
            ws.write(header_row,c,col,head); width=min(max(12,len(str(col))+2),34); ws.set_column(c,c,width)
        if len(df):
            ws.autofilter(header_row,0,header_row+len(df),len(df.columns)-1); ws.freeze_panes(header_row+1,0)
            for col in ['% Evaluación','% Checklist']:
                if col in df.columns: ws.set_column(df.columns.get_loc(col),df.columns.get_loc(col),14,pct)
            if 'Vigencia' in df.columns:
                c=df.columns.get_loc('Vigencia')
                ws.conditional_format(header_row+1,c,header_row+len(df),c,{'type':'text','criteria':'containing','value':'VENCIDO','format':wb.add_format({'bg_color':'#FFC7CE','font_color':'#9C0006'})})
                ws.conditional_format(header_row+1,c,header_row+len(df),c,{'type':'text','criteria':'containing','value':'POR VENCER','format':wb.add_format({'bg_color':'#FFEB9C','font_color':'#9C6500'})})
    out.seek(0); return out.getvalue()

def make_upload_template_excel():
    cols=["RUC","RAZON SOCIAL","NOMBRE COMERCIAL","TIPO","REPRESENTANTE LEGAL","CONTACTO","TELEFONO","CORREO",
          "DIRECCION","UBICACIÓN_FISICA","WEB","PRODUCTO / SERVICIO","RUC","INICIO DE OPERACIONES","INICIO SERVICIO",
          "BENEFICIARIOS","ESTADO","RESPONSABLE_CENASE","NOTAS"]
    out=io.BytesIO()
    with pd.ExcelWriter(out,engine='xlsxwriter') as writer:
        pd.DataFrame(columns=cols).to_excel(writer,index=False,sheet_name='PROVEEDORES',startrow=4)
        wb=writer.book; ws=writer.sheets['PROVEEDORES']
        titlefmt=wb.add_format({'bold':True,'font_color':'#17365D','font_size':16})
        head=wb.add_format({'bold':True,'font_color':'white','bg_color':'#4472C4','border':1,'align':'center','valign':'vcenter','text_wrap':True})
        ws.write('C1','CENASE - PLANTILLA CARGA MASIVA DE PROVEEDORES',titlefmt)
        if LOGO_PATH.exists():
            try: ws.insert_image('A1',str(LOGO_PATH),{'x_scale':0.65,'y_scale':0.65})
            except Exception: pass
        for c,col in enumerate(cols):
            ws.write(4,c,col,head); ws.set_column(c,c,22)
        ws.freeze_panes(5,0)
    out.seek(0); return out.getvalue()

def supplier_package(s,ass,key):
    zbuf=io.BytesIO(); folder=f"{clean_ruc(s.get('ruc'))}_{safe_filename(s.get('razon'))}"
    with zipfile.ZipFile(zbuf,'w',zipfile.ZIP_DEFLATED) as z:
        docs=[('acuerdo_completo','00_Acuerdo_Completo_CENASE_Anexo_BASC.pdf'),('conf','01_Acuerdo_Confidencialidad.pdf'),('seguridad','02_Acuerdo_Seguridad_BASC.pdf'),('verificacion','03_Registro_Verificacion.pdf'),('evaluacion','04_Evaluacion_Criticidad.pdf'),('plan','05_Plan_Accion.pdf'),('expediente','06_Expediente_BASC_Completo.pdf')]
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
if LOGO_PATH.exists():
    st.image(str(LOGO_PATH),width=230)
st.title("CENASE | Gestión BASC de Asociados de Negocio")
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
        st.download_button("📥 Plantilla Excel carga masiva",make_upload_template_excel(),"Plantilla_Proveedores_CENASE.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
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
            fields=[('n_proveedor','N° proveedor'),('razon','Razón social'),('ruc','RUC'),('nombre_comercial','Nombre comercial'),('tipo','Persona'),('representante','Representante legal'),('contacto','Contacto'),('telefono','Teléfono'),('email','Correo'),('direccion','Dirección legal'),('ubicacion_fisica','Ubicación física'),('web','Página web'),('servicio','Actividad con CENASE'),('actividad_ruc','Actividad principal RUC'),('inicio_operaciones','Inicio operaciones'),('inicio_servicio','Inicio servicio CENASE'),('responsable_cenase','Responsable CENASE')]
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

        # Documentos contractuales listos para firma
        s_current=st.session_state.suppliers.iloc[idx].to_dict(); key_current=supplier_key(s_current)
        ass_current=st.session_state.assess.get(key_current,{})
        ev_current=st.session_state.evidence.get(key_current,[])
        st.subheader("📝 Documentos para firma")
        st.caption("Los documentos se generan con los datos del proveedor seleccionado. Revise especialmente representante legal, dirección, teléfono y correo antes de firmar.")
        preview=pd.DataFrame([
            {"Campo":"Razón social","Dato":s_current.get('razon','')},
            {"Campo":"RUC","Dato":s_current.get('ruc','')},
            {"Campo":"Representante legal","Dato":s_current.get('representante','')},
            {"Campo":"Dirección","Dato":s_current.get('direccion','')},
            {"Campo":"Teléfono","Dato":s_current.get('telefono','')},
            {"Campo":"Correo","Dato":s_current.get('email','')},
            {"Campo":"Contacto","Dato":s_current.get('contacto','')},
            {"Campo":"Producto / servicio","Dato":s_current.get('servicio','')},
        ])
        st.dataframe(preview,use_container_width=True,hide_index=True)
        signing_missing=missing_fields(s_current)
        if signing_missing:
            st.error("Antes de enviar a firma completa estos datos: "+", ".join(signing_missing)+". El PDF puede descargarse para revisión, pero los campos faltantes aparecerán como PENDIENTE.")
        st.download_button("📝 DESCARGAR ACUERDO COMPLETO PARA FIRMA (FORMATO CENASE + ANEXO BASC)",build_pdf(s_current,'acuerdo_completo',ass_current,ev_current),f"{clean_ruc(s_current.get('ruc'))}_Acuerdo_Completo_CENASE_Anexo_BASC.pdf","application/pdf",key=f'sign_full_{key_current}',type="primary")
        d1,d2,d3=st.columns(3)
        d1.download_button("⬇️ Acuerdo confidencialidad PDF",build_pdf(s_current,'conf',ass_current,ev_current),f"{clean_ruc(s_current.get('ruc'))}_Acuerdo_Confidencialidad_CENASE.pdf","application/pdf",key=f'sign_conf_{key_current}')
        d2.download_button("⬇️ Acuerdo seguridad BASC PDF",build_pdf(s_current,'seguridad',ass_current,ev_current),f"{clean_ruc(s_current.get('ruc'))}_Acuerdo_Seguridad_BASC_CENASE.pdf","application/pdf",key=f'sign_sec_{key_current}')
        d3.download_button("📦 Paquete para firma",signing_package_zip(s_current,ass_current,ev_current),f"{clean_ruc(s_current.get('ruc'))}_{safe_filename(s_current.get('razon'))}_PARA_FIRMA.zip","application/zip",key=f'sign_zip_{key_current}')
        st.info(f"Firmas previstas: **{CENASE['representante']} - Gerente General de CENASE** y **{s_current.get('representante') or 'REPRESENTANTE LEGAL PENDIENTE'} - representante del proveedor**.")

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
        docs=[('acuerdo_completo','Acuerdo completo para firma','00_Acuerdo_Completo_CENASE_Anexo_BASC.pdf'),('conf','Acuerdo confidencialidad','01_Acuerdo_Confidencialidad.pdf'),('seguridad','Acuerdo seguridad BASC','02_Acuerdo_Seguridad_BASC.pdf'),('verificacion','Registro verificación','03_Registro_Verificacion.pdf'),('evaluacion','Evaluación criticidad','04_Evaluacion_Criticidad.pdf'),('plan','Plan de acción','05_Plan_Accion.pdf'),('expediente','Expediente completo','06_Expediente_BASC_Completo.pdf')]
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
                docs=[('acuerdo_completo','00_Acuerdo_Completo_CENASE_Anexo_BASC.pdf'),('conf','01_Acuerdo_Confidencialidad.pdf'),('seguridad','02_Acuerdo_Seguridad_BASC.pdf'),('verificacion','03_Registro_Verificacion.pdf'),('evaluacion','04_Evaluacion_Criticidad.pdf'),('plan','05_Plan_Accion.pdf'),('expediente','06_Expediente_BASC_Completo.pdf')]
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
