# ===== PES 2021 - Gerenciador de Jogadores e Times =====
# VERSÃO MODIFICADA: Suporte a LIGAS (linhas especiais na mesma lista) - Opção A + criação via Menu (Opção D)

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, messagebox, simpledialog
import json
import os
import sys
import io
import base64
import threading
import urllib.request
import unicodedata
import uuid
import time
import datetime
import webbrowser

# PIL/Pillow opcional — usado para bandeiras circulares sem fundo
try:
    from PIL import Image, ImageDraw, ImageOps, ImageTk
    _HAS_PIL  = True
    _RESAMPLE = getattr(Image, "LANCZOS", getattr(Image, "ANTIALIAS", 1))
except ImportError:
    _HAS_PIL = False

if getattr(sys, "frozen", False):
    # Rodando como executável compilado (PyInstaller) — usar a pasta onde
    # está o .exe, e não a pasta temporária de extração (_MEIPASS), senão
    # os dados salvos (times/jogadores) seriam perdidos a cada execução.
    _BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))

os.chdir(_BASE_DIR)

ARQUIVO_DADOS = "dados_pes2021.json"
ARQUIVO_CONFIG = "config.json"
ARQUIVO_HISTORICO = "historico_pes2021.json"

# ═══════════════════════════════════════════════════════════════════════════
# SISTEMA DE BANDEIRAS
# ═══════════════════════════════════════════════════════════════════════════
CODIGOS_PAISES = {
    "África do Sul":"za",  "Albânia":"al",            "Alemanha":"de",
    "Angola":"ao",         "Argentina":"ar",           "Argélia":"dz",
    "Armênia":"am",        "Arábia Saudita":"sa",      "Austrália":"au",
    "Áustria":"at",        "Bélgica":"be",             "Benim":"bj",
    "Bósnia e Herzegovina":"ba","Brasil":"br",          "Bulgária":"bg",
    "Bolívia":"bo",
    "Burkina Faso":"bf",   "Burundi":"bi",             "Cabo Verde":"cv",
    "Camarões":"cm",       "Canadá":"ca",              "Chile":"cl",
    "Chipre":"cy",         "Colômbia":"co",            "Comores":"km",
    "Coreia do Sul":"kr",  "Costa Rica":"cr",          "Costa do Marfim":"ci",
    "Croácia":"hr",        "Curaçao":"cw",             "Dinamarca":"dk",
    "Egito":"eg",          "Equador":"ec",             "Escócia":"gb-sct",
    "Eslováquia":"sk",     "Eslovênia":"si",           "Espanha":"es",
    "Estados Unidos":"us", "Estônia":"ee",             "Finlândia":"fi",
    "França":"fr",         "Gabão":"ga",               "Gana":"gh",
    "Geórgia":"ge",        "Grécia":"gr",              "Guadalupe":"gp",
    "Guiana Francesa":"gf","Guiné":"gn",               "Guiné Equatorial":"gq",
    "Guiné-Bissau":"gw",   "Gâmbia":"gm",              "Haiti":"ht",
    "Holanda":"nl",        "Honduras":"hn",            "Hungria":"hu",
    "Inglaterra":"gb-eng", "Indonésia":"id",           "Iraque":"iq",
    "Irlanda":"ie",        "Irlanda do Norte":"gb-nir","Irã":"ir",
    "Islândia":"is",       "Israel":"il",              "Itália":"it",
    "Jamaica":"jm",        "Japão":"jp",               "Jordânia":"jo",
    "Kosovo":"xk",         "Letônia":"lv",             "Libéria":"lr",
    "Lituânia":"lt",       "Luxemburgo":"lu",          "Líbia":"ly",
    "Macedônia do Norte":"mk","Madagascar":"mg",       "Mali":"ml",
    "Malásia":"my",        "Marrocos":"ma",            "Martinica":"mq",
    "Mauritânia":"mr",     "Moldávia":"md",            "Montenegro":"me",
    "Moçambique":"mz",     "México":"mx",              "Nigéria":"ng",
    "Noruega":"no",        "Nova Zelândia":"nz",       "Níger":"ne",
    "Panamá":"pa",         "Paraguai":"py",            "País de Gales":"gb-wls",
    "Peru":"pe",           "Polônia":"pl",             "Portugal":"pt",
    "R.D. Congo":"cd",     "República Centro-Africana":"cf",
    "República Dominicana":"do","República Tcheca":"cz",
    "Romênia":"ro",        "Ruanda":"rw",              "Rússia":"ru",
    "Senegal":"sn",        "Serra Leoa":"sl",          "Suriname":"sr",
    "Suécia":"se",         "Suíça":"ch",               "Sérvia":"rs",
    "Síria":"sy",          "Tanzânia":"tz",            "Togo":"tg",
    "Trinidad e Tobago":"tt",
    "Tunísia":"tn",        "Turquia":"tr",             "Ucrânia":"ua",
    "Uruguai":"uy",        "Uzbequistão":"uz",         "Venezuela":"ve",
    "Zâmbia":"zm",         "Zimbábue":"zw",
    # Especiais para ligas
    "UEFA / Europa":"eu",  "Reino Unido":"gb",
}

# Mudamos a pasta para forçar o download das novas imagens planas
PASTA_BANDEIRAS = os.path.join(_BASE_DIR, "bandeiras_planas")
_cache_nac: dict = {}       # nac -> tk.PhotoImage já composta (fundo branco padrão, p/ diálogos)
_cache_cod: dict = {}       # código -> tk.PhotoImage já composta (idem)
_cache_nac_rgba: dict = {}  # nac -> imagem PIL RGBA "crua" (com transparência real)
_cache_cod_rgba: dict = {}  # código -> imagem PIL RGBA "crua" (com transparência real)
_img_vazia       = None
_cache_gen       = 0   # incrementado a cada nova bandeira registrada (usado para saber quando redesenhar)


def _placeholder():
    global _img_vazia
    if _img_vazia is None:
        _img_vazia = tk.PhotoImage(width=28, height=28)
    return _img_vazia


def _png_para_circular(raw_bytes: bytes) -> "Image.Image":
    """
    Converte PNG de bandeira para uma imagem PIL RGBA com cantos arredondados
    e transparência alfa DE VERDADE (canal alpha), pronta para ser composta
    sobre qualquer cor de fundo sem deixar bordas visíveis.

    Também desenha um contorno bem sutil (quase imperceptível) ao redor da
    bandeira, para que bandeiras com muito branco (ex.: Japão) não "sumam"
    quando compostas sobre um fundo branco ou muito claro.
    """
    target_w, target_h = 32, 22  # Proporção mais comum para bandeiras planas
    radius = 4

    orig_img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    # ImageOps.fit garante que a imagem preencha o espaço sem distorcer
    flag_img = ImageOps.fit(orig_img, (target_w, target_h), _RESAMPLE)

    mask = Image.new("L", (target_w, target_h), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, target_w - 1, target_h - 1), radius=radius, fill=255)

    rgba = flag_img.convert("RGBA")
    rgba.putalpha(mask)

    # Contorno sutil: cinza escuro com baixa opacidade, 1px, com blending
    # real via canal alfa — fica quase imperceptível mas define a borda.
    contorno = ImageDraw.Draw(rgba, "RGBA")
    contorno.rounded_rectangle(
        (0, 0, target_w - 1, target_h - 1),
        radius=radius,
        outline=(90, 90, 90, 70),
        width=1,
    )
    return rgba


def _compor_sobre_fundo(rgba_img: "Image.Image", cor_rgb) -> "ImageTk.PhotoImage":
    """Compõe a bandeira (com transparência alfa) sobre uma cor de fundo
    sólida, gerando um bitmap opaco pronto para exibir em qualquer widget
    Tk comum (que não suporta transparência real por pixel)."""
    fundo = Image.new("RGB", rgba_img.size, cor_rgb)
    fundo.paste(rgba_img, (0, 0), rgba_img)
    return ImageTk.PhotoImage(fundo)


def _registrar(nac: str, data_b64: str):
    global _cache_gen
    try:
        raw = base64.b64decode(data_b64)
        cod = CODIGOS_PAISES.get(nac, "")
        if _HAS_PIL:
            rgba = _png_para_circular(raw)
            _cache_nac_rgba[nac] = rgba
            img = _compor_sobre_fundo(rgba, (255, 255, 255))
            if cod:
                _cache_cod_rgba[cod] = rgba
        else:
            img = tk.PhotoImage(data=data_b64)
        _cache_nac[nac] = img
        if cod:
            _cache_cod[cod] = img
        _cache_gen += 1
    except Exception:
        pass


def carregar_bandeiras(root, callback=None):
    os.makedirs(PASTA_BANDEIRAS, exist_ok=True)

    def _worker():
        for nac, cod in CODIGOS_PAISES.items():
            if nac in _cache_nac:
                continue
            arq = os.path.join(PASTA_BANDEIRAS, f"{cod}.png")
            if not os.path.exists(arq):
                try:
                    # NOVA FONTE: flagcdn fornece bandeiras planas por padrão no caminho /w320/
                    # O seu link anterior possivelmente estava pegando uma versão estilizada
                    url = f"https://flagcdn.com/w320/{cod}.png"
                    req = urllib.request.Request(url, headers={"User-Agent": "PES2021Manager"})
                    with urllib.request.urlopen(req, timeout=6) as r:
                        dados = r.read()
                    with open(arq, "wb") as f:
                        f.write(dados)
                except Exception:
                    continue
            try:
                with open(arq, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                root.after(0, lambda n=nac, d=b64: _registrar(n, d))
            except Exception:
                pass
        if callback:
            root.after(400, callback)

    threading.Thread(target=_worker, daemon=True).start()


# ── Mede largura de texto com o font real do Tkinter ─────────────────────
_fonte_cache = None

def _medir_texto(texto: str) -> int:
    global _fonte_cache
    try:
        if _fonte_cache is None:
            _fonte_cache = tkfont.nametofont("TkDefaultFont")
        w = _fonte_cache.measure(texto)
        if w >= len(texto) * 3:
            return w
    except Exception:
        pass
    return len(texto) * 8


_max_tw_nac_cache: int = 0

def _get_max_tw_nac() -> int:
    global _max_tw_nac_cache
    if _max_tw_nac_cache == 0:
        _max_tw_nac_cache = max((_medir_texto(n) for n in CODIGOS_PAISES), default=130)
    return _max_tw_nac_cache


def _ciclar_combobox(combobox, direcao):
    """Navega pelos valores de um ttk.Combobox usando as setas ↑/↓.
    Necessário porque o tema 'clam' (usado neste app) não implementa de
    forma confiável a navegação por teclado nativa dos comboboxes
    "readonly" — diferente do tema padrão do Windows."""
    valores = combobox["values"]
    if not valores:
        return "break"
    atual = combobox.get()
    try:
        idx = list(valores).index(atual)
    except ValueError:
        idx = -1 if direcao > 0 else len(valores)
    novo_idx = (idx + direcao) % len(valores)
    combobox.set(valores[novo_idx])
    combobox.event_generate("<<ComboboxSelected>>")
    return "break"


def _habilitar_setas_combobox(combobox):
    """Liga as setas ↑/↓ do teclado a _ciclar_combobox para um combobox
    readonly específico."""
    combobox.bind("<Up>", lambda e: _ciclar_combobox(combobox, -1))
    combobox.bind("<Down>", lambda e: _ciclar_combobox(combobox, 1))


# ── Bandeiras fixas (widgets filhos da própria tabela) ──────────────────
# Antes, as bandeiras eram desenhadas numa janela (Toplevel) separada,
# sobreposta à tabela via um truque de transparência, e reposicionada a
# cada evento. O problema é estrutural: duas janelas do Windows nunca ficam
# 100% sincronizadas durante um arrasto interativo — sempre sobra folga de
# alguns frames entre elas, não importa a rapidez do reposicionamento. Por
# isso as bandeiras "flutuavam" ao mover o programa.
#
# Agora as bandeiras são widgets tk.Label FILHOS da própria Treeview,
# posicionados com .place(). Por serem parte da mesma janela do SO, o
# Windows os move e redesenha junto com o resto do programa como um único
# bloco — não há mais nada para sincronizar, então não há mais como
# flutuar. Como bônus, elas também nunca mais aparecem por cima de outras
# janelas (diálogos de edição etc.), porque não são mais uma janela
# separada "sempre no topo".
class OverlayBandeiras:
    def __init__(self, root, tree,
                 col_nac: str = None,
                 col_liga: str = None,
                 get_img_liga=None):
        self.root         = root
        self.tree         = tree
        self.col_nac      = col_nac
        self.col_liga     = col_liga
        self.get_img_liga = get_img_liga
        self._job         = None
        self._last_sig    = None   # última "assinatura" do conteúdo desenhado
        self._last_draw   = 0.0    # timestamp do último _desenhar() (usado pelo throttle em _agendar)
        self._pool_nac    = []     # tk.Label reutilizáveis (bandeiras de nacionalidade)
        self._pool_liga   = []     # tk.Label reutilizáveis (bandeiras de liga)
        self._cache_compostas = {} # (id(rgba), cor) -> PhotoImage já composta

        for ev in ("<Configure>", "<<TreeviewSelect>>"):
            tree.bind(ev, self._agendar, add="+")
        # Roda do mouse por si só não é confiável aqui: as bindings de
        # instância (a nossa) disparam ANTES das bindings de classe do Tk
        # que de fato realizam a rolagem, então redesenharíamos com a
        # posição antiga. Já a barra de rolagem nem dispara <MouseWheel>.
        # O único ponto por onde QUALQUER rolagem passa — roda do mouse,
        # arrastar a barra, teclado (Home/End/Page Up/Down) — é o callback
        # "yscrollcommand" da própria tabela. Interceptamos ele aqui: assim
        # cobrimos todas as formas de rolar de uma vez só, sempre depois
        # que a posição já mudou de verdade.
        self._enganchar_yscroll()
        self._loop()

    def _enganchar_yscroll(self):
        comando_original = self.tree.cget("yscrollcommand")

        def _wrapper(lo, hi):
            if comando_original:
                try:
                    self.tree.tk.call(comando_original, lo, hi)
                except tk.TclError:
                    pass
            self._agendar()

        self.tree.configure(yscrollcommand=_wrapper)

    def _loop(self):
        # Rede de segurança para casos em que o conteúdo muda sem disparar
        # nenhum dos eventos escutados acima (raro).
        self._desenhar()
        self.tree.after(500, self._loop)

    def forcar(self):
        """Força um redesenho completo, ignorando a assinatura em cache.
        Usar quando dados mudam (ex.: bandeira de liga atribuída) sem que
        rolagem, seleção ou quantidade de linhas tenham mudado."""
        self._last_sig = None
        self._desenhar()

    def _agendar(self, _=None):
        # Throttle (não debounce): garante no máximo uma chamada pendente
        # em vez de cancelar/reagendar a cada evento (o que faria o
        # redesenho nunca rodar durante uma rajada de eventos).
        agora = time.monotonic()
        if agora - self._last_draw >= 0.03:
            self._last_draw = agora
            self._desenhar()
        elif not self._job:
            self._job = self.tree.after(30, self._agendar_pendente)

    def _agendar_pendente(self):
        self._job = None
        self._last_draw = time.monotonic()
        self._desenhar()

    def _cor_fundo_item(self, item):
        """Aproxima a cor de fundo atual da linha (selecionada, com tag
        colorida, ou padrão) para compor a bandeira sem deixar bordas
        visíveis ao redor dos cantos arredondados."""
        style = ttk.Style()
        try:
            if item in self.tree.selection():
                cor = style.lookup("Treeview", "background", ("selected",))
                if cor:
                    return cor
                return "#0078d7"
        except tk.TclError:
            pass
        try:
            tags = self.tree.item(item, "tags") or ()
        except tk.TclError:
            tags = ()
        for t in tags:
            try:
                conf = self.tree.tag_configure(t)
            except tk.TclError:
                continue
            bg = conf.get("background") if conf else None
            if bg:
                valor = bg[-1] if isinstance(bg, (tuple, list)) else bg
                if valor:
                    return valor
        return style.lookup("Treeview", "background") or "white"

    def _rgb_de(self, cor):
        """Resolve qualquer especificação de cor do Tk (hex, nome, ou cor
        de sistema como 'SystemHighlight') para uma tupla RGB de 8 bits,
        usando o próprio widget para consultar a cor real renderizada."""
        try:
            r16, g16, b16 = self.tree.winfo_rgb(cor)
            return (r16 // 256, g16 // 256, b16 // 256)
        except tk.TclError:
            return (255, 255, 255)

    def _compor(self, rgba_img, cor):
        """Compõe a bandeira (com transparência alfa real) sobre a cor de
        fundo da linha, com cache por (imagem, cor) para não reprocessar a
        cada redesenho."""
        chave = (id(rgba_img), cor)
        cache_hit = self._cache_compostas.get(chave)
        if cache_hit is not None:
            return cache_hit
        foto = _compor_sobre_fundo(rgba_img, self._rgb_de(cor))
        self._cache_compostas[chave] = foto
        return foto

    def _obter_label(self, pool, idx):
        if idx < len(pool):
            return pool[idx]
        lbl = tk.Label(self.tree, bd=0, highlightthickness=0)
        pool.append(lbl)
        return lbl

    def _linhas_visiveis(self, tree):
        """Retorna só os itens realmente visíveis na área rolável da tabela
        agora — evitando percorrer TODAS as linhas (potencialmente milhares,
        como na lista geral de jogadores) a cada redesenho. Antes, isso só
        não pesava porque o bug da assinatura fazia o redesenho ser pulado
        na maioria das vezes; corrigido aquele bug, o custo de percorrer a
        lista inteira ficou visível ao trocar de aba.

        Usa as frações de rolagem (yview) em vez de identify_row(0): a
        coordenada y=0 cai em cima do CABEÇALHO da tabela (Nome/Time/...),
        não na primeira linha de dados, então identify_row(0) não achava
        nada — e as bandeiras só apareciam depois de rolar."""
        todos = tree.get_children()
        n = len(todos)
        if n == 0:
            return todos
        if tree.winfo_height() < 4:
            return ()
        try:
            frac_topo, frac_base = tree.yview()
        except tk.TclError:
            return todos  # fallback conservador: melhor processar tudo do que nada

        aprox_inicio = int(frac_topo * n)
        aprox_fim    = int(frac_base * n) + 1

        # Margem de segurança para pequenas variações de altura de linha
        i0 = max(0, aprox_inicio - 2)
        i1 = min(n - 1, aprox_fim + 2)
        return todos[i0:i1 + 1]

    def _desenhar(self, _=None):
        tree = self.tree
        tree.update_idletasks()

        if not tree.winfo_viewable() or tree.winfo_width() < 4:
            for lbl in self._pool_nac + self._pool_liga:
                lbl.place_forget()
            # Crucial: invalida a assinatura salva. Sem isso, quando a aba
            # (ou a janela minimizada) voltar a ficar visível, nada terá
            # mudado no conteúdo (mesmo tamanho, rolagem, seleção...) e o
            # desenho seria pulado por "achar" que já está em dia — deixando
            # as bandeiras escondidas até algo mudar a seleção/foco (ex.:
            # um clique). Zerando aqui, forçamos o redesenho completo assim
            # que a tabela ficar visível de novo.
            self._last_sig = None
            return

        try:
            sig = (tree.winfo_width(), tree.winfo_height(), tree.yview(),
                   len(tree.get_children()), tree.selection(), tree.focus(),
                   _cache_gen)
        except tk.TclError:
            sig = None
        if sig is not None and sig == self._last_sig:
            return
        self._last_sig = sig

        cols = list(tree["columns"])
        bw, bh = 32, 22
        usados_nac  = 0
        usados_liga = 0

        if self.col_nac and self.col_nac in cols:
            nac_idx  = cols.index(self.col_nac)
            fixed_fx = None
            pendente = []

            for item in self._linhas_visiveis(tree):
                vals = tree.item(item, "values")
                if not vals:
                    continue
                nac = vals[nac_idx]
                rgba = _cache_nac_rgba.get(nac)
                if not rgba:
                    continue
                cell = tree.bbox(item, column=self.col_nac)
                if not cell:
                    continue
                if fixed_fx is None:
                    fixed_fx = cell[0] + 5
                pendente.append((item, cell, rgba))

            for item, cell, rgba in pendente:
                _, cy, _, ch = cell
                cor = self._cor_fundo_item(item)
                img = self._compor(rgba, cor)
                lbl = self._obter_label(self._pool_nac, usados_nac)
                lbl.configure(image=img, bg=cor)
                lbl.image = img
                lbl.place(x=fixed_fx, y=cy + (ch - bh) // 2, width=bw, height=bh)
                usados_nac += 1

        if self.col_liga and self.get_img_liga and self.col_liga in cols:
            liga_idx   = cols.index(self.col_liga)
            col_espaco = "U" if "U" in cols else self.col_liga

            for item in self._linhas_visiveis(tree):
                vals = tree.item(item, "values")
                tags = tree.item(item, "tags")
                if "liga" not in tags or not vals:
                    continue
                nome = vals[liga_idx]
                rgba = self.get_img_liga(nome)
                if not rgba:
                    continue
                cell = tree.bbox(item, column=col_espaco)
                if not cell:
                    continue
                cx, cy, cw, ch = cell
                fx = cx + (cw - bw) // 2
                fy = cy + (ch - bh) // 2
                cor = self._cor_fundo_item(item)
                img = self._compor(rgba, cor)
                lbl = self._obter_label(self._pool_liga, usados_liga)
                lbl.configure(image=img, bg=cor)
                lbl.image = img
                lbl.place(x=fx, y=fy, width=bw, height=bh)
                usados_liga += 1

        # Esconde labels do pool que sobraram sem uso nesta rodada
        for lbl in self._pool_nac[usados_nac:]:
            lbl.place_forget()
        for lbl in self._pool_liga[usados_liga:]:
            lbl.place_forget()

# TIME ESPECIAL - Jogadores sem time fixo
TIME_LIVRES = "Jogadores Livres"

# === NACIONALIDADES ===
NACIONALIDADES_ORIGINAL = [
    "África do Sul", "Alemanha", "Angola", "Argentina", "Austrália", "Áustria",
    "Bolívia", "Brasil", "Bulgária", "Cabo Verde", "Camarões", "Canadá", "Chile",
    "Colômbia", "Coreia do Sul", "Costa Rica", "Croácia", "Dinamarca", "Equador",
    "Egito", "Escócia", "Eslováquia", "Eslovênia", "Espanha", "Estados Unidos",
    "Estônia", "Finlândia", "Gabão", "Gana", "Geórgia", "Grécia", "Honduras",
    "Holanda", "Inglaterra", "Irlanda", "Irlanda do Norte", "Islândia", "Israel",
    "Itália", "Burkina Faso", "Japão", "Lituânia", "México", "Montenegro", "Nigéria", "Noruega",
    "Nova Zelândia", "País de Gales", "Paraguai", "Peru", "Portugal", "R.D. Congo",
    "República Tcheca", "Rússia", "Sérvia", "Suécia", "Suíça", "Turquia", "Uruguai",
    "Uzbequistão", "Venezuela", "França", "Senegal", "Bélgica", "Marrocos", "Guiné", "Ucrânia",
    "Hungria", "Argélia", "Polônia", "Romênia", "Armênia", "Kosovo", "Costa do Marfim", "Macedônia do Norte", 
    "Mali", "Panamá", "Jamaica", "República Centro-Africana", "Bósnia e Herzegovina", "Luxemburgo", "República Dominicana",
    "Moçambique", "Curaçao", "Albânia", "Tunísia", "Síria", "Indonésia", "Irã", "Jordânia", "Zimbábue", "Burundi",
    "Libéria", "Serra Leoa", "Zâmbia", "Gâmbia", "Suriname", "Guiné-Bissau", "Haiti", "Guadalupe", "Mauritânia", "Arábia Saudita", "Benim", "Guiné Equatorial", "Chipre", "Togo", "Iraque", "Comores", "Tanzânia", "Líbia", "Guiana Francesa", "Malásia", "Níger", "Letônia", "Moldávia", "Ruanda"

]

def remover_acentos(texto):
    # Mapeamento manual para caracteres que a normalização NFD não resolve (ex: Ø, ø, Æ, æ, Đ, đ)
    substituicoes = {
        'ø': 'o', 'Ø': 'O',
        'æ': 'ae', 'Æ': 'AE',
        'đ': 'd', 'Đ': 'D',
        'ł': 'l', 'Ł': 'L',
        'ß': 'ss',
        'þ': 'th', 'Þ': 'TH'
    }
    for char, sub in substituicoes.items():
        texto = texto.replace(char, sub)
    
    return ''.join(c for c in unicodedata.normalize('NFD', texto)
                   if unicodedata.category(c) != 'Mn').lower()

NACIONALIDADES = sorted(NACIONALIDADES_ORIGINAL, key=lambda x: remover_acentos(x))

# === POSIÇÕES BRASILEIRAS ===
POSICOES_BR = {
    "GOL": "GOL", "ZAG": "ZAG", "LD": "LD", "LE": "LE", "VOL": "VOL",
    "MLG": "MLG", "MLD": "MLD", "MLE": "MLE", "MAT": "MAT",
    "PTD": "PTD", "PTE": "PTE", "SA": "SA", "CA": "CA"
}
POSICOES_LISTA = [
    "GOL", "ZAG", "LD", "LE",
    "VOL", "MLG", "MLD", "MLE", "MAT",
    "PTD", "PTE", "SA", "CA"
]

MAP_PES_TO_BR = {
    "GK": "GOL", "CB": "ZAG", "LB": "LE", "RB": "LD", "DMF": "VOL",
    "CMF": "MLG", "LMF": "MLE", "RMF": "MLD", "AMF": "MAT",
    "LWF": "PTE", "RWF": "PTD", "SS": "SA", "CF": "CA"
}
MAP_BR_TO_PES = {v: k for k, v in MAP_PES_TO_BR.items()}

# === CARREGAR E SALVAR DADOS ===
def converter_posicoes_pes_para_br(lista_pes):
    return [MAP_PES_TO_BR.get(p, p) for p in lista_pes if p in MAP_PES_TO_BR]

def converter_posicoes_br_para_pes(lista_br):
    return [MAP_BR_TO_PES.get(p, p) for p in lista_br if p in MAP_BR_TO_PES]

def carregar_dados():
    # Retorna (dados, ordem_original)
    if os.path.exists(ARQUIVO_DADOS):
        try:
            with open(ARQUIVO_DADOS, 'r', encoding='utf-8') as f:
                dados = json.load(f)
                ordem_original = dados.get("ordem_times", list(dados["times"].keys()))

                # Normalizar estrutura: suportar times antigos e ler ligas (obj com "liga": True)
                for nome, time in list(dados["times"].items()):
                    if isinstance(time, dict) and time.get("liga", False):
                        # é uma liga — nada a fazer
                        continue
                    # Caso normal - time com jogadores
                    for j in time["jogadores"]:
                        j.setdefault("camisa", "")
                        j.setdefault("nacionalidade", "")
                        j.setdefault("posicoes_secundarias", [])
                        j.setdefault("nome_completo", "")
                        j.setdefault("verificar_camisa", False)

                        if "id" not in j:
                            j["id"] = str(uuid.uuid4())

                        pos_pes = j.get("posicao", "")
                        j["posicao"] = MAP_PES_TO_BR.get(pos_pes, pos_pes)
                        sec_pes = j.get("posicoes_secundarias", [])
                        j["posicoes_secundarias"] = converter_posicoes_pes_para_br(sec_pes)

                    time.setdefault("editado", False)
                    time.setdefault("nacionalidade", "")
                    time.setdefault("uniforme_editado", False)
                    orig_ord = time.get("ordem", [j["id"] for j in time.get("jogadores", [])])

                    if orig_ord and isinstance(orig_ord, list):
                        todos_ids = {j["id"] for j in time.get("jogadores", [])}
                        if all(item in todos_ids for item in orig_ord):
                            time["ordem"] = orig_ord
                        else:
                            nova_ord = []
                            for nome_item in orig_ord:
                                encontrado = next((p for p in time["jogadores"] if p["nome"] == nome_item), None)
                                if encontrado:
                                    nova_ord.append(encontrado["id"])
                            for p in time["jogadores"]:
                                if p["id"] not in nova_ord:
                                    nova_ord.append(p["id"])
                            time["ordem"] = nova_ord
                    else:
                        time["ordem"] = [j["id"] for j in time.get("jogadores", [])]

                # Garantir TIME_LIVRES presente como time normal (não liga)
                if TIME_LIVRES not in dados["times"]:
                    dados["times"][TIME_LIVRES] = {"jogadores": [], "ordem": [], "editado": False}
                if TIME_LIVRES not in ordem_original:
                    ordem_original.append(TIME_LIVRES)
                
                dados.setdefault("anotacoes", "")

                return dados, ordem_original
        except Exception as e:
            print(f"Erro ao carregar dados: {e}")
            return {"times": {TIME_LIVRES: {"jogadores": [], "ordem": [], "editado": False}}, "anotacoes": ""}, [TIME_LIVRES]
    # se não existe arquivo
    return {"times": {TIME_LIVRES: {"jogadores": [], "ordem": [], "editado": False}}, "anotacoes": ""}, [TIME_LIVRES]

def salvar_dados(dados, ordem_original):
    try:
        dados_salvar = {
            "ordem_times": ordem_original,
            "times": {},
            "anotacoes": dados.get("anotacoes", "")
        }
        for nome in ordem_original:
            # salvar na ordem: se existir em dados, ajustar
            time = dados["times"].get(nome)
            if not time:
                # se não estiver em dados (por algum motivo), pular
                continue
            if isinstance(time, dict) and time.get("liga", False):
                # liga -> salvar como objeto com "liga": True
                dados_salvar["times"][nome] = {"liga": True}
                continue
            # time normal
            editado = False if nome == TIME_LIVRES else time.get("editado", False)
            time_salvar = {
                "jogadores": [],
                "ordem": time.get("ordem", []),
                "editado": editado,
                "nacionalidade": time.get("nacionalidade", ""),
                "uniforme_editado": time.get("uniforme_editado", False)
            }
            for j in time["jogadores"]:
                j_salvar = j.copy()
                pos_br = j_salvar.get("posicao", "")
                j_salvar["posicao"] = MAP_BR_TO_PES.get(pos_br, pos_br)
                sec_br = j_salvar.get("posicoes_secundarias", [])
                j_salvar["posicoes_secundarias"] = converter_posicoes_br_para_pes(sec_br)
                time_salvar["jogadores"].append(j_salvar)
            dados_salvar["times"][nome] = time_salvar
        with open(ARQUIVO_DADOS, 'w', encoding='utf-8') as f:
            json.dump(dados_salvar, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Erro ao salvar dados: {e}")

# === CARREGAR E SALVAR CONFIGURAÇÃO ===
def carregar_config():
    if os.path.exists(ARQUIVO_CONFIG):
        try:
            with open(ARQUIVO_CONFIG, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return {
                    "width": config.get("width", 1350),
                    "height": config.get("height", 780),
                    "col_widths_jog": config.get("col_widths_jog", {}),
                    "col_widths_jog_time": config.get("col_widths_jog_time", {}),
                    "col_widths_times": config.get("col_widths_times", {}),
                    "bandeiras_ligas": config.get("bandeiras_ligas", {})
                }
        except Exception as e:
            print(f"Erro ao carregar config: {e}")
    return {"width": 1350, "height": 780, "col_widths_jog": {},
            "col_widths_jog_time": {}, "col_widths_times": {}, "bandeiras_ligas": {}}

def salvar_config(app):
    try:
        cols_jog      = ("Nome", "Time", "Posição", "Overall", "Nacionalidade")
        cols_jog_time = ("Nome", "Camisa", "Posição", "Overall", "Nacionalidade")

        col_widths_jog      = {c: app.tree_jog.column(c, 'width')      for c in cols_jog}
        col_widths_jog_time = {c: app.tree_jog_time.column(c, 'width') for c in cols_jog_time}
        col_widths_times    = {c: app.tree_times.column(c, 'width')    for c in ("U", "Time", "Média", "Jogadores")}

        config = {
            "width":               app.config["width"],
            "height":              app.config["height"],
            "col_widths_jog":      col_widths_jog,
            "col_widths_jog_time": col_widths_jog_time,
            "col_widths_times":    col_widths_times,
            "bandeiras_ligas":     app.bandeiras_ligas,
        }
        with open(ARQUIVO_CONFIG, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        print(f"Erro ao salvar config: {e}")

# === CARREGAR E SALVAR HISTÓRICO ===
def carregar_historico():
    # Retorna (lista_historico, arquivo_ja_existia)
    if os.path.exists(ARQUIVO_HISTORICO):
        try:
            with open(ARQUIVO_HISTORICO, 'r', encoding='utf-8') as f:
                return json.load(f), True
        except Exception as e:
            print(f"Erro ao carregar histórico: {e}")
            return [], True
    return [], False

def salvar_historico(lista):
    try:
        with open(ARQUIVO_HISTORICO, 'w', encoding='utf-8') as f:
            json.dump(lista, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Erro ao salvar histórico: {e}")

# === MENU DE CONTEXTO (copiar/colar) PARA CAMPOS DE TEXTO ===
def _menu_contexto_campo_texto(event):
    widget = event.widget
    try:
        widget.focus_set()
    except Exception:
        pass

    menu = tk.Menu(widget, tearoff=0)

    def _executar(acao):
        try:
            if acao == "recortar":
                widget.event_generate("<<Cut>>")
            elif acao == "copiar":
                widget.event_generate("<<Copy>>")
            elif acao == "colar":
                widget.event_generate("<<Paste>>")
            elif acao == "selecionar_tudo":
                if isinstance(widget, tk.Text):
                    widget.tag_add("sel", "1.0", "end")
                else:
                    widget.selection_range(0, tk.END)
        except Exception:
            pass

    # Campos somente-leitura (ex.: Combobox readonly) não permitem recortar/colar
    somente_leitura = False
    try:
        somente_leitura = "readonly" in widget.state()
    except Exception:
        pass

    menu.add_command(label="Recortar", command=lambda: _executar("recortar"), state=("disabled" if somente_leitura else "normal"))
    menu.add_command(label="Copiar", command=lambda: _executar("copiar"))
    menu.add_command(label="Colar", command=lambda: _executar("colar"), state=("disabled" if somente_leitura else "normal"))
    menu.add_separator()
    menu.add_command(label="Selecionar Tudo", command=lambda: _executar("selecionar_tudo"))

    try:
        menu.tk_popup(event.x_root, event.y_root)
    finally:
        menu.grab_release()


# === JANELA DE EDIÇÃO ===
def abrir_janela_edicao(root, app, jogador_ref, time_nome, callback):
    win = tk.Toplevel(root)
    win.title("Editar Jogador")
    win.geometry("700x690")
    win.transient(root)
    win.grab_set()
    win.resizable(False, False)
    win.update_idletasks()
    x = (win.winfo_screenwidth() // 2) - (win.winfo_width() // 2)
    y = (win.winfo_screenheight() // 2) - (win.winfo_height() // 2)
    win.geometry(f"+{x}+{y}")

    frame = ttk.Frame(win, padding=20)
    frame.pack(fill="both", expand=True)
    cb_vars = {}
    checkbuttons = []

    f_dados_principais = ttk.LabelFrame(frame, text="Dados Principais", padding=15)
    f_dados_principais.pack(fill="x", pady=(0, 12))
    f_dados_principais.grid_columnconfigure(0, weight=1)
    f_dados_principais.grid_columnconfigure(1, weight=1)

    ttk.Label(f_dados_principais, text="Nome:", font=("Helvetica", 10)).grid(row=0, column=0, sticky="w", pady=(0, 5))
    e_nome = ttk.Entry(f_dados_principais, width=44, font=("Helvetica", 10))
    e_nome.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 12))
    e_nome.insert(0, jogador_ref["nome"])
    e_nome.bind("<Return>", lambda e: salvar_edicao())

    ttk.Label(f_dados_principais, text="Nome Completo (opcional):", font=("Helvetica", 10)).grid(row=2, column=0, sticky="w", pady=(0, 5))
    e_nome_completo = ttk.Entry(f_dados_principais, width=44, font=("Helvetica", 10))
    e_nome_completo.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 12))
    e_nome_completo.insert(0, jogador_ref.get("nome_completo", ""))
    e_nome_completo.bind("<Return>", lambda e: salvar_edicao())

    ttk.Label(f_dados_principais, text="Link do Transfermarkt (opcional):", font=("Helvetica", 10)).grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, 5))
    f_link = ttk.Frame(f_dados_principais)
    f_link.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(0, 12))
    f_link.grid_columnconfigure(0, weight=1)
    e_link = ttk.Entry(f_link, font=("Helvetica", 10))
    e_link.grid(row=0, column=0, sticky="ew")
    e_link.insert(0, jogador_ref.get("link_transfermarkt", ""))
    e_link.bind("<Return>", lambda e: salvar_edicao())

    def abrir_link_transfermarkt():
        link = e_link.get().strip()
        if not link:
            messagebox.showinfo("Sem link", "Nenhum link foi preenchido para este jogador.", parent=win)
            return
        if not (link.startswith("http://") or link.startswith("https://")):
            link = "https://" + link
        webbrowser.open(link)

    ttk.Button(f_link, text="Abrir", command=abrir_link_transfermarkt).grid(row=0, column=1, padx=(8, 0))

    ttk.Label(f_dados_principais, text="Posição Principal:", font=("Helvetica", 10)).grid(row=6, column=0, sticky="w", pady=(0, 5))
    cb_pos = ttk.Combobox(f_dados_principais, values=list(POSICOES_BR.keys()), state="readonly", width=16)
    cb_pos.grid(row=7, column=0, sticky="w", pady=(0, 12))
    cb_pos.set(jogador_ref["posicao"])
    _habilitar_setas_combobox(cb_pos)

    ttk.Label(f_dados_principais, text="Overall (0-99):", font=("Helvetica", 10)).grid(row=6, column=1, sticky="w", padx=(30, 0), pady=(0, 5))
    e_ovr = ttk.Entry(f_dados_principais, width=12)
    e_ovr.grid(row=7, column=1, sticky="w", padx=(30, 0), pady=(0, 12))
    e_ovr.insert(0, str(jogador_ref["overall"]))
    e_ovr.bind("<Return>", lambda e: salvar_edicao())

    ttk.Label(f_dados_principais, text="Camisa (1-99):", font=("Helvetica", 10)).grid(row=8, column=0, sticky="w", pady=(0, 5))
    e_camisa = ttk.Entry(f_dados_principais, width=12)
    e_camisa.grid(row=9, column=0, sticky="w", pady=(0, 12))
    e_camisa.insert(0, jogador_ref["camisa"])
    e_camisa.bind("<Return>", lambda e: salvar_edicao())

    ttk.Label(f_dados_principais, text="Nacionalidade:", font=("Helvetica", 10)).grid(row=8, column=1, sticky="w", padx=(30, 0), pady=(0, 5))
    cb_nac = ttk.Combobox(f_dados_principais, values=NACIONALIDADES, width=28)
    cb_nac.grid(row=9, column=1, sticky="w", padx=(30, 0), pady=(0, 12))
    cb_nac.set(jogador_ref.get("nacionalidade", ""))

    def autocompletar_nac(e):
        if e.keysym in ["BackSpace", "Delete", "Left", "Right", "Up", "Down", "Tab", "Return"]:
            return
        
        typed = cb_nac.get()
        
        # Lógica de busca por letra: APENAS se o campo estiver vazio e uma letra for digitada.
        # Isso simula a navegação por letra quando o dropdown está aberto e o usuário
        # quer ir para a primeira nacionalidade que começa com aquela letra.
        if not typed and e.char and len(e.char) == 1:
            char = e.char.lower()
            for i, nac in enumerate(NACIONALIDADES):
                if remover_acentos(nac).lower().startswith(char):
                    cb_nac.current(i)
                    return "break"
        
        # Lógica de autocompletar: se o campo não estiver vazio, autocompleta.
        if not typed:
            return
        
        typed_lower = remover_acentos(typed).lower()
        matches = [nac for nac in NACIONALIDADES if remover_acentos(nac).lower().startswith(typed_lower)]
        if matches:
            match = matches[0]
            cb_nac.set(match)
            cb_nac.selection_range(len(typed), tk.END)
            
    cb_nac.bind("<KeyRelease>", autocompletar_nac)

    f_pos_secundarias = ttk.LabelFrame(frame, text="Posições Secundárias", padding=(15, 10, 15, 15))
    f_pos_secundarias.pack(fill="x", pady=(0, 12))

    colunas_max = 4
    for i in range(colunas_max):
        f_pos_secundarias.grid_columnconfigure(i, weight=1, uniform="pos")

    for i, pos in enumerate(POSICOES_LISTA):
        row = i // colunas_max
        col = i % colunas_max
        cb_vars[pos] = tk.BooleanVar(value=(pos in jogador_ref.get("posicoes_secundarias", [])))
        cb = ttk.Checkbutton(f_pos_secundarias, text=pos, variable=cb_vars[pos],
                             style="Secundaria.TCheckbutton")
        cb.grid(row=row, column=col, sticky="w", padx=10, pady=4)
        checkbuttons.append(cb)
        if pos == jogador_ref["posicao"]:
            cb.state(['disabled'])

    style = ttk.Style(win)
    style.configure("Secundaria.TCheckbutton", font=("Helvetica", 10, "bold"), foreground="black")
    style.map("Secundaria.TCheckbutton", foreground=[('disabled', 'gray'), ('selected', '#28a745')])

    def check_pos_principal_change(event):
        nova_pos_principal = cb_pos.get()
        for pos, var in cb_vars.items():
            for child in f_pos_secundarias.winfo_children():
                if isinstance(child, ttk.Checkbutton) and child['text'] == pos:
                    if pos == nova_pos_principal:
                        var.set(False)
                        child.state(['disabled'])
                    else:
                        child.state(['!disabled'])
                    break
    cb_pos.bind("<<ComboboxSelected>>", check_pos_principal_change)
    check_pos_principal_change(None)

    btn_frame = ttk.Frame(frame)
    btn_frame.pack(pady=18)

    def salvar_edicao(event=None):
        try:
            novo_nome = e_nome.get().strip()
            if not novo_nome:
                messagebox.showerror("Erro", "Nome não pode estar vazio!", parent=win)
                return

            nova_pos = cb_pos.get()
            if nova_pos not in POSICOES_BR:
                messagebox.showerror("Erro", "Selecione uma posição válida!", parent=win)
                return

            ovr_input = e_ovr.get().strip()
            if not ovr_input.isdigit():
                messagebox.showerror("Erro", "Overall deve ser um número de 0 a 99!", parent=win)
                return
            novo_ovr = int(ovr_input)
            if not 0 <= novo_ovr <= 99:
                messagebox.showerror("Erro", "Overall deve estar entre 0 e 99!", parent=win)
                return

            camisa_input = e_camisa.get().strip()
            camisa = ""
            if camisa_input:
                if not camisa_input.isdigit():
                    messagebox.showerror("Erro", "Camisa deve ser um número de 1 a 99!", parent=win)
                    return
                camisa_num = int(camisa_input)
                if not 1 <= camisa_num <= 99:
                    messagebox.showerror("Erro", "Camisa deve estar entre 1 a 99!", parent=win)
                    return
                camisa = str(camisa_num)

                if time_nome != TIME_LIVRES:
                    for j in app.dados["times"][time_nome]["jogadores"]:
                        if j.get("camisa", "") == camisa and j["id"] != jogador_ref["id"]:
                            messagebox.showerror("Erro", f"Nº {camisa_num} já está em uso neste time!", parent=win)
                            return

            nac = cb_nac.get().strip()
            
            # Validar se a nacionalidade está na lista oficial
            if nac and nac not in NACIONALIDADES:
                messagebox.showerror("Erro", f"A nacionalidade '{nac}' não é válida!", parent=win)
                return
                
            novas_pos_sec = [pos for pos, var in cb_vars.items() if var.get() and pos != nova_pos]
            novo_nome_completo = e_nome_completo.get().strip()
            novo_link = e_link.get().strip()

            # Capturar valores anteriores ANTES de sobrescrever, para registrar
            # no histórico exatamente o que mudou, campo a campo.
            campos_rotulo = {
                "nome": "Nome",
                "posicao": "Posição",
                "overall": "Overall",
                "camisa": "Camisa",
                "nacionalidade": "Nacionalidade",
                "posicoes_secundarias": "Posições secundárias",
                "nome_completo": "Nome completo",
                "link_transfermarkt": "Link Transfermarkt",
            }
            valores_antigos = {campo: jogador_ref.get(campo) for campo in campos_rotulo}

            jogador_ref["nome"] = novo_nome
            jogador_ref["posicao"] = nova_pos
            jogador_ref["overall"] = novo_ovr
            jogador_ref["camisa"] = camisa
            jogador_ref["nacionalidade"] = nac
            jogador_ref["posicoes_secundarias"] = novas_pos_sec
            jogador_ref["nome_completo"] = novo_nome_completo
            jogador_ref["link_transfermarkt"] = novo_link
            jogador_ref["verificar_camisa"] = False

            valores_novos = {campo: jogador_ref.get(campo) for campo in campos_rotulo}
            mudancas = []
            for campo, rotulo in campos_rotulo.items():
                antigo = valores_antigos.get(campo)
                novo = valores_novos.get(campo)
                if antigo != novo:
                    mudancas.append(f"{rotulo}: '{antigo}' → '{novo}'")

            if mudancas:
                app.registrar_historico("Edição", novo_nome, time_nome, "; ".join(mudancas))

            salvar_dados(app.dados, app.ordem_original)
            callback()
            win.destroy()
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao salvar: {e}", parent=win)

    def cancelar(event=None):
        win.destroy()

    btn_salvar = ttk.Button(btn_frame, text="Salvar", command=salvar_edicao)
    btn_salvar.pack(side="left", padx=12)
    ttk.Button(btn_frame, text="Cancelar", command=cancelar).pack(side="left", padx=12)

    e_ovr.bind("<Up>", lambda e: app.ajustar_valor_teclado(e, e_ovr, 0, 99))
    e_ovr.bind("<Down>", lambda e: app.ajustar_valor_teclado(e, e_ovr, 0, 99))
    e_camisa.bind("<Up>", lambda e: app.ajustar_valor_teclado(e, e_camisa, 1, 99))
    e_camisa.bind("<Down>", lambda e: app.ajustar_valor_teclado(e, e_camisa, 1, 99))

    campos = [e_nome, e_nome_completo, e_link, cb_pos, e_ovr, e_camisa, cb_nac] + checkbuttons + [btn_salvar]

    def focus_next(event):
        cur = event.widget
        try:
            idx = campos.index(cur)
            next_idx = (idx + 1) % len(campos)
            campos[next_idx].focus_set()
        except:
            pass
        return "break"

    def focus_prev(event):
        cur = event.widget
        try:
            idx = campos.index(cur)
            prev_idx = (idx - 1) % len(campos)
            campos[prev_idx].focus_set()
        except:
            pass
        return "break"

    for campo in campos:
        try:
            campo.bind("<Tab>", focus_next)
            campo.bind("<Shift-Tab>", focus_prev)
        except Exception:
            pass

    for cb in checkbuttons:
        def toggle_cb(event, c=cb):
            if 'disabled' not in c.state():
                var = cb_vars[c['text']]
                var.set(not var.get())
            return "break"
        cb.bind("<Return>", toggle_cb)
        cb.bind("<space>", toggle_cb)

    win.bind("<Return>", lambda e: salvar_edicao() if win.focus_get() == btn_salvar else None)
    win.bind("<Escape>", lambda e: cancelar())
    e_nome.focus_set()
    win.protocol("WM_DELETE_WINDOW", cancelar)


# === APP ===
class App:
    def __init__(self, root):
        self.root = root
        self.root.title("PES 2021 Overhall")

        # Ícones removidos - mantida apenas funcionalidade de marcar times como editados

        self.config = carregar_config()
        width = self.config["width"]
        height = self.config["height"]
        self.root.geometry(f"{width}x{height}")
        self.root.minsize(1100, 650)
        self.centralizar_janela()

        # Menu de copiar/colar (botão direito) em TODOS os campos de texto do
        # programa, atuais e futuros - inclusive em janelas abertas depois
        # (edição de jogador, diálogos, etc.), pois o bind é por classe de widget.
        self.root.bind_class("TEntry", "<Button-3>", _menu_contexto_campo_texto)
        self.root.bind_class("TCombobox", "<Button-3>", _menu_contexto_campo_texto)
        self.root.bind_class("Text", "<Button-3>", _menu_contexto_campo_texto)

        dados, self.ordem_original = carregar_dados()
        self.dados = dados

        self.historico, historico_ja_existia = carregar_historico()
        if not historico_ja_existia:
            self._preencher_historico_inicial()

        self.time_selecionado = None
        self.times_ordenado_por = None
        self.time_search_buffer = ""
        self.time_search_timer = None
        self.jogador_search_buffer = ""
        self.jogador_search_timer = None

        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TNotebook.Tab", padding=[18, 10], font=("Helvetica", 11, "bold"))

        style.configure("Treeview", rowheight=30, fieldbackground="#cccccc", borderwidth=2, relief="solid")
        style.configure("Treeview.Heading", font=("Helvetica", 10, "bold"))
        style.map("Treeview", background=[("selected", "#0056b3")])
        style.layout("Treeview", [('Treeview.treearea', {'sticky': 'nswe', 'border': '1'}), ('Treeview.padding', {'sticky': 'nswe', 'border': '1'})])

        self.nb = ttk.Notebook(root)
        self.nb.pack(fill="both", expand=True, padx=18, pady=18)

        self.pagina_jogadores = ttk.Frame(self.nb)
        self.pagina_times = ttk.Frame(self.nb)
        self.pagina_anotacoes = ttk.Frame(self.nb)
        self.pagina_historico = ttk.Frame(self.nb)
        self.nb.add(self.pagina_jogadores, text="Jogadores")
        self.nb.add(self.pagina_times, text="Times")
        self.nb.add(self.pagina_anotacoes, text="Anotações")
        self.nb.add(self.pagina_historico, text="Histórico")

        self.montar_jogadores()
        self.montar_times()
        self.montar_anotacoes()
        self.montar_historico()

        self.root.bind("<Configure>", self.on_configure)
        self.root.bind("<Control-Tab>", lambda e: self.nb.select((self.nb.index("current") + 1) % 4))
        self.root.bind("<Control-Shift-Tab>", lambda e: self.nb.select((self.nb.index("current") - 1) % 4))
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Menu de contexto para jogadores (já existente)
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Editar", command=self.menu_editar)
        self.context_menu.add_command(label="Transferir", command=self.menu_transferir)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Liberar (Free Agent)", command=self.menu_liberar)


    def centralizar_janela(self):
        self.root.update_idletasks()
        w, h = self.root.winfo_width(), self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (w // 2)
        y = (self.root.winfo_screenheight() // 2) - (h // 2)
        self.root.geometry(f"+{x}+{y}")

    def on_configure(self, event):
        if event.widget == self.root:
            width = self.root.winfo_width()
            height = self.root.winfo_height()
            if width >= 1100 and height >= 650:
                self.config["width"] = width
                self.config["height"] = height

    def on_closing(self):
        # Garantir que anotações sejam salvas antes de fechar
        if hasattr(self, 'txt_anotacoes'):
            self.dados["anotacoes"] = self.txt_anotacoes.get("1.0", "end-1c")
        salvar_dados(self.dados, self.ordem_original)
        salvar_config(self)
        self.root.destroy()

    def ajustar_valor_teclado(self, event, entry_widget, min_val, max_val):
        try:
            txt = entry_widget.get().strip()
            if txt == "" and event.keysym == "Up":
                entry_widget.insert(0, str(min_val))
                return "break"
            if not txt.isdigit():
                return "break"
            val = int(txt)
            if event.keysym == "Up":
                val = min(val + 1, max_val)
            elif event.keysym == "Down":
                val = max(val - 1, min_val)
            else:
                return "break"
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, str(val))
        except:
            pass
        return "break"

    # === LÓGICA DO MENU DE CONTEXTO E TRANSFERÊNCIA ===

    def exibir_menu_contexto(self, event, tree):
        item = tree.identify_row(event.y)
        if item:
            tree.selection_set(item)
            tree.focus(item)
            self.context_menu.post(event.x_root, event.y_root)

    def obter_jogador_selecionado(self):
        tab_index = self.nb.index("current")
        if tab_index == 0:
            tree = self.tree_jog
            sel = tree.selection()
            if not sel: return None, None
            jogador_id = sel[0]
            v = tree.item(jogador_id, "values")
            time_nome = v[1]
            return jogador_id, time_nome
        else:
            tree = self.tree_jog_time
            sel = tree.selection()
            if not sel: return None, None
            jogador_id = sel[0]
            time_nome = self.time_selecionado
            return jogador_id, time_nome

    def menu_editar(self):
        tab_index = self.nb.index("current")
        if tab_index == 0:
            self.duplo_clique_jogador()
        else:
            self.duplo_clique_jogador_time()

    def menu_transferir(self):
        jid, time_origem = self.obter_jogador_selecionado()
        if not jid or not time_origem: return
        self.dialogo_transferencia(jid, time_origem)

    def menu_liberar(self):
        jid, time_origem = self.obter_jogador_selecionado()
        if not jid or not time_origem: return

        t = self.dados["times"].get(time_origem)
        jog = next((j for j in t["jogadores"] if j["id"] == jid), None)
        if not jog: return

        if time_origem == TIME_LIVRES:
            messagebox.showinfo("Info", "Este jogador já está livre.")
            return

        if messagebox.askyesno("Liberar Jogador", f"Deseja enviar {jog['nome']} para {TIME_LIVRES}?"):
            self.realizar_transferencia(jid, time_origem, TIME_LIVRES)

    def dialogo_transferencia(self, jid, time_origem):
        win = tk.Toplevel(self.root)
        win.title("Transferir Jogador")
        win.geometry("350x450")
        win.transient(self.root)
        win.grab_set()

        win.update_idletasks()
        x = (win.winfo_screenwidth() // 2) - (win.winfo_width() // 2)
        y = (win.winfo_screenheight() // 2) - (win.winfo_height() // 2)
        win.geometry(f"+{x}+{y}")

        ttk.Label(win, text="Selecione o time de destino:", font=("Helvetica", 11, "bold")).pack(pady=10)

        # Agrupar times por liga, mantendo a ordem original (personalizada pelo usuário)
        # Cada grupo é (nome_da_liga_ou_None, [times_do_grupo])
        grupos = []
        grupo_nome = None
        grupo_times = []
        for nome in self.ordem_original:
            if nome not in self.dados["times"]:
                continue
            info = self.dados["times"][nome]
            if info.get("liga", False):
                grupos.append((grupo_nome, grupo_times))
                grupo_nome = nome
                grupo_times = []
            elif nome != time_origem:
                grupo_times.append(nome)
        grupos.append((grupo_nome, grupo_times))
        grupos = [(g_nome, g_times) for g_nome, g_times in grupos if g_times]

        frame_lista = ttk.Frame(win)
        frame_lista.pack(fill="both", expand=True, padx=20, pady=5)

        scrollbar = ttk.Scrollbar(frame_lista)
        scrollbar.pack(side="right", fill="y")

        lb = tk.Listbox(frame_lista, yscrollcommand=scrollbar.set, font=("Helvetica", 10))
        lb.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=lb.yview)

        # Insere os times na listbox, com uma linha divisória (não selecionável)
        # antes de cada grupo de liga
        headers_idx = set()
        mapa_idx_time = {}
        idx = 0
        for g_nome, g_times in grupos:
            if g_nome is not None:
                lb.insert(tk.END, f"▬▬▬ {g_nome} ▬▬▬")
                lb.itemconfig(idx, fg="#1a5276", selectbackground=lb.cget("background"), selectforeground="#1a5276")
                headers_idx.add(idx)
                mapa_idx_time[idx] = None
                idx += 1
            for t in g_times:
                lb.insert(tk.END, t)
                mapa_idx_time[idx] = t
                idx += 1

        def _proximo_item_valido(a_partir_de):
            for i in range(a_partir_de + 1, lb.size()):
                if i not in headers_idx:
                    return i
            for i in range(a_partir_de - 1, -1, -1):
                if i not in headers_idx:
                    return i
            return None

        def evitar_selecao_header(event=None):
            sel = lb.curselection()
            if not sel:
                return
            if sel[0] in headers_idx:
                novo = _proximo_item_valido(sel[0])
                lb.selection_clear(0, tk.END)
                if novo is not None:
                    lb.selection_set(novo)
                    lb.activate(novo)
                    lb.see(novo)

        lb.bind("<<ListboxSelect>>", evitar_selecao_header)

        # Lógica de busca por teclado no Listbox
        win.search_buffer = ""
        
        def buscar_na_lista(event):
            if not event.char or len(event.char) != 1:
                return
            
            char = event.char.lower()
            items = lb.get(0, tk.END)
            if not items:
                return
            
            current_sel = lb.curselection()
            start_idx = (current_sel[0] + 1) if current_sel else 0
            
            # Se for a mesma letra, continua do próximo. Se for nova, começa do topo.
            if char != win.search_buffer:
                win.search_buffer = char
                start_idx = 0
            
            char_sem_acento = remover_acentos(char)
            
            # Busca circular (ignorando as linhas divisórias de liga)
            for i in range(len(items)):
                idx = (start_idx + i) % len(items)
                if idx in headers_idx:
                    continue
                item_text = remover_acentos(items[idx]).lower()
                if item_text.startswith(char_sem_acento):
                    lb.selection_clear(0, tk.END)
                    lb.selection_set(idx)
                    lb.activate(idx)
                    lb.see(idx)
                    break

        lb.bind("<Key>", buscar_na_lista)
        lb.bind("<Double-1>", lambda e: confirmar())
        lb.bind("<Return>", lambda e: confirmar())
        lb.focus_set()

        def confirmar():
            sel = lb.curselection()
            if not sel or sel[0] in headers_idx:
                messagebox.showwarning("Atenção", "Selecione um time de destino!", parent=win)
                return
            destino = mapa_idx_time[sel[0]]
            self.realizar_transferencia(jid, time_origem, destino)
            win.destroy()

        btn_frame = ttk.Frame(win)
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text="Transferir", command=confirmar).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancelar", command=win.destroy).pack(side="left", padx=5)

    def realizar_transferencia(self, jogador_id, time_origem, time_destino):
        t_orig = self.dados["times"][time_origem]
        jogador = next((j for j in t_orig["jogadores"] if j["id"] == jogador_id), None)

        if not jogador: return

        t_orig["jogadores"].remove(jogador)
        if jogador_id in t_orig.get("ordem", []):
            t_orig["ordem"].remove(jogador_id)

        t_dest = self.dados["times"][time_destino]

        if time_destino == TIME_LIVRES:
            jogador["camisa"] = ""
            jogador["verificar_camisa"] = False
        else:
            camisas_usadas = set()
            for p in t_dest["jogadores"]:
                c = p.get("camisa", "")
                if c.isdigit():
                    camisas_usadas.add(int(c))

            # Jogadores transferidos ficam sem número de camisa até que o usuário arrume
            jogador["camisa"] = ""
            jogador["verificar_camisa"] = True

        t_dest["jogadores"].append(jogador)
        t_dest.setdefault("ordem", [])
        t_dest["ordem"].append(jogador_id)

        salvar_dados(self.dados, self.ordem_original)
        self.registrar_historico("Transferência", jogador.get("nome", ""), time_destino,
                                  f"Transferido de '{time_origem}' para '{time_destino}'")
        self.atualizar_tudo()

        if time_destino != TIME_LIVRES:
            messagebox.showinfo("Sucesso", "Transferido")

    # ---------- Aba Jogadores ----------
    def montar_jogadores(self):
        frame = self.pagina_jogadores
        ttk.Label(frame, text="Todos os Jogadores Cadastrados", font=("Helvetica", 14, "bold")).pack(pady=(0, 12))

        f_filtros = ttk.LabelFrame(frame, text="Filtros")
        f_filtros.pack(fill="x", padx=10, pady=5)

        ttk.Label(f_filtros, text="Buscar:").grid(row=0, column=0, padx=5, pady=5)
        self.e_buscar = ttk.Entry(f_filtros, width=25)
        self.e_buscar.grid(row=0, column=1, padx=5)

        ttk.Label(f_filtros, text="País:").grid(row=0, column=2, padx=5)
        self.cb_filtro_pais = ttk.Combobox(f_filtros, values=["Todos"] + NACIONALIDADES, width=20)
        self.cb_filtro_pais.grid(row=0, column=3, padx=5)
        self.cb_filtro_pais.set("Todos")

        ttk.Label(f_filtros, text="Pos:").grid(row=0, column=4, padx=5)
        self.cb_filtro_pos = ttk.Combobox(f_filtros, values=["Todas"] + list(POSICOES_BR.keys()), state="readonly", width=10)
        self.cb_filtro_pos.grid(row=0, column=5, padx=5)
        self.cb_filtro_pos.set("Todas")
        _habilitar_setas_combobox(self.cb_filtro_pos)

        ttk.Label(f_filtros, text="Liga:").grid(row=0, column=6, padx=5)
        self.cb_filtro_liga = ttk.Combobox(f_filtros, values=["Todas"], state="readonly", width=20)
        self.cb_filtro_liga.grid(row=0, column=7, padx=5)
        self.cb_filtro_liga.set("Todas")
        _habilitar_setas_combobox(self.cb_filtro_liga)

        btn_limpar = ttk.Button(f_filtros, text="Limpar", command=self.limpar_filtros)
        btn_limpar.grid(row=0, column=8, padx=8)



        # Rodapé para contadores na aba Jogadores (criado antes para garantir posição)
        f_rodape_jog = ttk.LabelFrame(frame, text="Estatísticas")
        f_rodape_jog.pack(side="bottom", fill="x", padx=10, pady=5)

        self.lbl_cont_total = ttk.Label(f_rodape_jog, text="Total: 0", font=("Helvetica", 10, "bold"))
        self.lbl_cont_total.pack(side="left", padx=20, pady=5)

        tree_frame_jog = ttk.Frame(frame, padding=(10, 0, 10, 5))
        tree_frame_jog.pack(fill="both", expand=True)

        v_scroll_jog = ttk.Scrollbar(tree_frame_jog, orient="vertical")
        v_scroll_jog.pack(side="right", fill="y")
        h_scroll_jog = ttk.Scrollbar(tree_frame_jog, orient="horizontal")
        h_scroll_jog.pack(side="bottom", fill="x")

        cols = ("Nome", "Time", "Posição", "Overall", "Nacionalidade")
        self.tree_jog = ttk.Treeview(tree_frame_jog, columns=cols, show="headings", height=20,
                                     yscrollcommand=v_scroll_jog.set, xscrollcommand=h_scroll_jog.set, style="Treeview")
        v_scroll_jog.config(command=self.tree_jog.yview)
        h_scroll_jog.config(command=self.tree_jog.xview)

        for c in cols:
            self.tree_jog.heading(c, text=c, command=lambda col=c: self.ordenar_por(col))
            align = "center" if c != "Nome" else "w"
            self.tree_jog.column(c, anchor=align, minwidth=0, stretch=True)

        self.tree_jog.tag_configure("atencao", foreground="red")

        col_widths = self.config.get("col_widths_jog", {})
        if col_widths:
            for col in cols:
                w = col_widths.get(col)
                if w is not None:
                    self.tree_jog.column(col, width=w, minwidth=0, stretch=True)
        else:
            self.tree_jog.column("Nome", width=250, minwidth=0, stretch=True)
            self.tree_jog.column("Time", width=150, minwidth=0, stretch=True)
            self.tree_jog.column("Posição", width=100, minwidth=0, stretch=True)
            self.tree_jog.column("Overall", width=100, minwidth=0, stretch=True)
            self.tree_jog.column("Nacionalidade", width=150, minwidth=0, stretch=True)

        self.tree_jog.pack(fill="both", expand=True)

        btns = ttk.Frame(frame)
        btns.pack(pady=12)
        self.btn_remover_geral = ttk.Button(btns, text="Remover Selecionado (Del)", command=self.remover_jogador_geral)
        self.btn_remover_geral.pack(side="left", padx=8)

        self.tree_jog.bind("<Double-1>", self.duplo_clique_jogador)
        self.tree_jog.bind("<Return>", self.duplo_clique_jogador)
        self.tree_jog.bind("<Delete>", lambda e: self.remover_jogador_geral())
        self.tree_jog.bind("<Button-3>", lambda e: self.exibir_menu_contexto(e, self.tree_jog))
        self.tree_jog.bind("<Button-2>", lambda e: self.selecionar_por_clique_meio(e, self.tree_jog))

        self.e_buscar.bind("<KeyRelease>", lambda e: self.aplicar_filtros())
        self.cb_filtro_pais.bind("<KeyRelease>", self.autocompletar_filtro_pais)
        self.cb_filtro_pais.bind("<<ComboboxSelected>>", lambda e: self.aplicar_filtros())
        self.cb_filtro_pos.bind("<<ComboboxSelected>>", lambda e: self.aplicar_filtros())
        self.cb_filtro_liga.bind("<<ComboboxSelected>>", lambda e: self.aplicar_filtros())

        self.tree_jog.bind("<Tab>", lambda e: self.proximo_foco(e, self.btn_remover_geral))
        self.tree_jog.bind("<Shift-Tab>", lambda e: self.anterior_foco(e, self.e_buscar))
        self.tree_jog.bind("<Home>", self.selecionar_primeiro_jogador_geral)
        self.tree_jog.bind("<End>", self.selecionar_ultimo_jogador_geral)

        self.coluna_ordenada = "Overall"
        self.ordem_desc = True
        
        self.coluna_ordenada_time = None
        self.ordem_desc_time = False
        
        self.atualizar_jogadores_geral()

    def autocompletar_filtro_pais(self, e):
        typed = self.cb_filtro_pais.get().strip()
        if not typed or typed == "Todos":
            self.cb_filtro_pais.selection_clear()
            return
        typed_lower = remover_acentos(typed)
        matches = [nac for nac in ["Todos"] + NACIONALIDADES if remover_acentos(nac).startswith(typed_lower)]
        if matches:
            self.cb_filtro_pais.set(matches[0])
            self.cb_filtro_pais.selection_range(len(typed), tk.END)
        else:
            self.cb_filtro_pais.selection_clear()
        self.aplicar_filtros()

    def aplicar_filtros(self):
        self.atualizar_jogadores_geral()

    def limpar_filtros(self):
        self.e_buscar.delete(0, tk.END)
        self.cb_filtro_pais.set("Todos")
        self.cb_filtro_pos.set("Todas")
        self.cb_filtro_liga.set("Todas")
        self.atualizar_jogadores_geral()

    def atualizar_jogadores_geral(self):
        for i in self.tree_jog.get_children():
            self.tree_jog.delete(i)

        jogadores = []
        for time_nome, time_data in self.dados["times"].items():
            # pular ligas
            if time_data.get("liga", False):
                continue
            for j in time_data["jogadores"]:
                j_copy = j.copy()
                j_copy["time"] = time_nome
                jogadores.append(j_copy)

        # Mantém o combobox de ligas sincronizado com as ligas existentes
        # (podem ser criadas/renomeadas/excluídas a qualquer momento).
        ligas_existentes = [nome for nome in self.ordem_original
                             if self.dados["times"].get(nome, {}).get("liga", False)]
        valores_liga = ["Todas"] + ligas_existentes
        if tuple(self.cb_filtro_liga["values"]) != tuple(valores_liga):
            selecao_atual = self.cb_filtro_liga.get()
            self.cb_filtro_liga["values"] = valores_liga
            if selecao_atual in valores_liga:
                self.cb_filtro_liga.set(selecao_atual)
            else:
                self.cb_filtro_liga.set("Todas")

        buscar = remover_acentos(self.e_buscar.get().lower())
        pais_filtro = self.cb_filtro_pais.get()
        pos_filtro = self.cb_filtro_pos.get()
        liga_filtro = self.cb_filtro_liga.get()

        jogadores_filtrados = jogadores

        if buscar:
            termos = buscar.split()
            def match_jogador(j):
                nome_j = remover_acentos(j["nome"].lower())
                nome_completo_j = remover_acentos(j.get("nome_completo", "").lower())
                time_j = remover_acentos(j["time"].lower())
                # Deve conter todos os termos da busca em qualquer parte do nome, nome completo ou time
                return all(t in nome_j or t in nome_completo_j or t in time_j for t in termos)
            jogadores_filtrados = [j for j in jogadores_filtrados if match_jogador(j)]

        if pais_filtro != "Todos":
            jogadores_filtrados = [j for j in jogadores_filtrados if j.get("nacionalidade", "") == pais_filtro]

        if pos_filtro != "Todas":
            jogadores_filtrados = [j for j in jogadores_filtrados if j["posicao"] == pos_filtro or pos_filtro in j.get("posicoes_secundarias", [])]

        if liga_filtro != "Todas":
            jogadores_filtrados = [j for j in jogadores_filtrados if self.obter_liga_do_time(j["time"]) == liga_filtro]

        def get_sort_key(j):
            # Normalizamos a string para a ordenação ser consistente
            nome_norm = remover_acentos(j["nome"]).lower()
            time_norm = remover_acentos(j["time"]).lower()
            pais_norm = remover_acentos(j.get("nacionalidade", "")).lower()
            
            if self.coluna_ordenada == "Nome":
                # Se desc: Nome Z->A, Overall (ajudado pelo reverse=True)
                # Se asc: Nome A->Z, Overall (ajudado pelo reverse=False)
                return (nome_norm, -j["overall"]) if not self.ordem_desc else (nome_norm, j["overall"])
            elif self.coluna_ordenada == "Time":
                return (time_norm, -j["overall"], nome_norm) if not self.ordem_desc else (time_norm, j["overall"], nome_norm)
            elif self.coluna_ordenada == "Posição":
                idx_pos = POSICOES_LISTA.index(j["posicao"])
                return (idx_pos, -j["overall"], nome_norm) if not self.ordem_desc else (idx_pos, j["overall"], nome_norm)
            elif self.coluna_ordenada == "Overall":
                # Se reverse=True (padrão do Overall): Overall 99->0, Nome A->Z
                # Para Nome ser A->Z com reverse=True, precisamos inverter o valor ou usar um truque
                # Truque: Como strings não invertem fácil, vamos tratar o caso do Overall separadamente
                return (j["overall"], [-(ord(c)) for c in nome_norm])
            elif self.coluna_ordenada == "Nacionalidade":
                return (pais_norm, -j["overall"], nome_norm) if not self.ordem_desc else (pais_norm, j["overall"], nome_norm)
            return ""

        if pos_filtro != "Todas":
            # Ordenação base
            jogadores_filtrados.sort(key=get_sort_key, reverse=self.ordem_desc)
            # Fixar posição filtrada no topo
            jogadores_filtrados.sort(key=lambda j: j["posicao"] == pos_filtro, reverse=True)
        else:
            jogadores_filtrados.sort(key=get_sort_key, reverse=self.ordem_desc)

        cont_livres = 0
        for j in jogadores_filtrados:
            tags = []
            if j.get("verificar_camisa", False):
                tags.append("atencao")
            
            if j["time"] == TIME_LIVRES:
                cont_livres += 1

            self.tree_jog.insert("", "end", iid=j["id"],
                                 values=(j["nome"], j["time"], j["posicao"], j["overall"], j.get("nacionalidade", "")),
                                 tags=tags)

        # Atualizar label de contagem total
        self.lbl_cont_total.config(text=f"Total: {len(jogadores_filtrados)}")

        # A lista foi repopulada (dados podem ter mudado, ex.: nacionalidade
        # editada) — força o overlay a redesenhar mesmo que contagem/seleção
        # de linhas tenham ficado iguais.
        if hasattr(self, "_ov_jog"):
            self._ov_jog.forcar()

    def ordenar_por(self, col):
        if self.coluna_ordenada == col:
            self.ordem_desc = not self.ordem_desc
        else:
            self.coluna_ordenada = col
            self.ordem_desc = True if col in ["Overall"] else False
        self.atualizar_jogadores_geral()

    def duplo_clique_jogador(self, event=None):
        sel = self.tree_jog.selection()
        if not sel: return
        jogador_id = sel[0]
        v = self.tree_jog.item(jogador_id, "values")
        time_nome = v[1]
        time_data = self.dados["times"].get(time_nome)
        if not time_data: return
        jogador_ref = next((j for j in time_data["jogadores"] if j["id"] == jogador_id), None)
        if not jogador_ref: return

        abrir_janela_edicao(
            self.root, self, jogador_ref, time_nome,
            lambda: self.manter_selecao_jogador_geral(jogador_id, time_nome)
        )

    def selecionar_por_clique_meio(self, event, tree):
        """Clique do botão do meio (scroll) seleciona o item sob o cursor,
        igual a um clique esquerdo normal - funciona em qualquer lista
        (times ou jogadores)."""
        row = tree.identify_row(event.y)
        if row:
            tree.selection_set(row)
            tree.focus(row)
            tree.see(row)
        return "break"

    def manter_selecao_jogador_geral(self, jogador_id, nome_time):
        self.atualizar_tudo()
        for item_id in self.tree_jog.get_children():
            if item_id == jogador_id:
                values = self.tree_jog.item(item_id, "values")
                if values[1] == nome_time:
                    self.tree_jog.selection_set(item_id)
                    self.tree_jog.focus(item_id)
                    self.tree_jog.see(item_id)
                    break

    def remover_jogador_geral(self):
        sel = self.tree_jog.selection()
        if not sel:
            messagebox.showwarning("Atenção", "Selecione um jogador para remover!")
            return
        jogador_id = sel[0]
        v = self.tree_jog.item(jogador_id, "values")
        nome = v[0]
        time_nome = v[1]
        if messagebox.askyesno("Remover", f"Remover {nome} do {time_nome}?"):
            t = self.dados["times"][time_nome]
            jogador = next((j for j in t["jogadores"] if j["id"] == jogador_id), None)
            if jogador:
                t["jogadores"].remove(jogador)
            try:
                t["ordem"].remove(jogador_id)
            except ValueError:
                pass
            salvar_dados(self.dados, self.ordem_original)
            self.registrar_historico("Remoção", nome, time_nome, "Jogador removido do time")
            self.atualizar_tudo()

    # ---------- Aba Times ----------
    def montar_times(self):
        frame = self.pagina_times
        left = ttk.Frame(frame)
        left.pack(side="left", fill="y", padx=(0, 10))

        ttk.Label(left, text="Times", font=("Helvetica", 14, "bold")).pack(pady=(0, 12))

        f_novo = ttk.LabelFrame(left, text="Novo Time")
        f_novo.pack(fill="x", padx=10, pady=5)

        ttk.Label(f_novo, text="Nome:").pack(side="left", padx=5, pady=5)
        self.e_novo_time = ttk.Entry(f_novo, font=("Helvetica", 10))
        self.e_novo_time.pack(side="left", fill="x", expand=True, padx=5, pady=5)
        self.btn_add_time = ttk.Button(f_novo, text="Adicionar", command=self.add_time)
        self.btn_add_time.pack(side="right", padx=5)
        self.e_novo_time.bind("<Return>", lambda e: self.add_time())

        # Barra de Pesquisa de Times
        f_busca_time = ttk.LabelFrame(left, text="Buscar Time")
        f_busca_time.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(f_busca_time, text="Nome:").pack(side="left", padx=5, pady=5)
        self.e_buscar_time = ttk.Entry(f_busca_time, font=("Helvetica", 10))
        self.e_buscar_time.pack(side="left", fill="x", expand=True, padx=5, pady=5)
        self.e_buscar_time.bind("<KeyRelease>", lambda e: self.atualizar_times())

        tree_frame_times = ttk.Frame(left, padding=(10, 5, 10, 5))
        tree_frame_times.pack(fill="both", expand=True)

        v_scroll_times = ttk.Scrollbar(tree_frame_times, orient="vertical")
        v_scroll_times.pack(side="right", fill="y")

        cols_time = ("U", "Time", "Média", "Jogadores")
        self.tree_times = ttk.Treeview(tree_frame_times, columns=cols_time, show="headings", height=15,
                                       yscrollcommand=v_scroll_times.set, style="Treeview")
        v_scroll_times.config(command=self.tree_times.yview)

        self.tree_times.heading("U", text="U")
        self.tree_times.heading("Time", text="Time")
        self.tree_times.heading("Média", text="Média", command=self.ordenar_times_por_media)
        self.tree_times.heading("Jogadores", text="Jogadores")
        
        col_widths_times = self.config.get("col_widths_times", {})
        if col_widths_times:
            for col in cols_time:
                w = col_widths_times.get(col)
                if w is not None:
                    align = "center" if col != "Time" else "w"
                    self.tree_times.column(col, width=w, anchor=align, minwidth=0, stretch=True)
        else:
            self.tree_times.column("U", width=30, anchor="center", minwidth=0, stretch=True)
            self.tree_times.column("Time", width=200, anchor="w", minwidth=0, stretch=True)
            self.tree_times.column("Média", width=80, anchor="center", minwidth=0, stretch=True)
            self.tree_times.column("Jogadores", width=80, anchor="center", minwidth=0, stretch=True)
        self.tree_times.pack(fill="both", expand=True)

        # tags: cores de fundo para times editados/não editados e ligas
        self.tree_times.tag_configure("editado", background="#c3e6cb")
        self.tree_times.tag_configure("nao_editado", background="white")
        self.tree_times.tag_configure("atencao_time", foreground="red")
        # self.tree_times.tag_configure("negrito", font=("Helvetica", 10, "bold"))
        # Liga: Destaque maior com fonte maior e cor de fundo cinza mais escuro
        try:
            self.tree_times.tag_configure("liga", background="#d9d9d9", font=("Helvetica", 12, "bold"))
        except Exception:
            # algumas versões não aceitam font em tag_configure; então apenas cor
            self.tree_times.tag_configure("liga", background="#d9d9d9")

        btns_time = ttk.Frame(left)
        btns_time.pack(pady=8)
        self.btn_renomear = ttk.Button(btns_time, text="Renomear (F2)", command=self.renomear_time)
        self.btn_renomear.pack(side="left", padx=6)
        self.btn_excluir = ttk.Button(btns_time, text="Excluir (Del)", command=self.excluir_time)
        self.btn_excluir.pack(side="left", padx=6)

        self.lbl_rodape = ttk.Label(left, text="", font=("Helvetica", 10, "bold"), foreground="black")
        self.lbl_rodape.pack(pady=(5, 0))

        right = ttk.Frame(frame)
        right.pack(side="right", fill="both", expand=True, padx=(10, 0))

        self.lbl_time = ttk.Label(right, text="Selecione um time", font=("Helvetica", 14, "bold"))
        self.lbl_time.pack(pady=(0, 10))

        f_jog = ttk.LabelFrame(right, text="Adicionar Jogador")
        f_jog.pack(fill="x", padx=10, pady=5)

        ttk.Label(f_jog, text="Nome:").grid(row=0, column=0, padx=5, pady=5)
        self.e_nome_jog = ttk.Entry(f_jog, width=20)
        self.e_nome_jog.grid(row=0, column=1, padx=5)
        ttk.Label(f_jog, text="Pos:").grid(row=0, column=2, padx=5)
        self.cb_pos = ttk.Combobox(f_jog, values=list(POSICOES_BR.keys()), state="readonly", width=8)
        self.cb_pos.grid(row=0, column=3, padx=5)
        _habilitar_setas_combobox(self.cb_pos)
        ttk.Label(f_jog, text="OVR:").grid(row=0, column=4, padx=5)
        self.e_ovr = ttk.Entry(f_jog, width=6)
        self.e_ovr.grid(row=0, column=5, padx=5)
        self.e_ovr.bind("<Up>", lambda e: self.ajustar_valor_teclado(e, self.e_ovr, 0, 99))
        self.e_ovr.bind("<Down>", lambda e: self.ajustar_valor_teclado(e, self.e_ovr, 0, 99))
        ttk.Label(f_jog, text="Nº:").grid(row=0, column=6, padx=5)
        self.e_camisa = ttk.Entry(f_jog, width=5)
        self.e_camisa.grid(row=0, column=7, padx=5)
        self.e_camisa.bind("<Up>", lambda e: self.ajustar_valor_teclado(e, self.e_camisa, 1, 99))
        self.e_camisa.bind("<Down>", lambda e: self.ajustar_valor_teclado(e, self.e_camisa, 1, 99))
        ttk.Label(f_jog, text="Nac:").grid(row=0, column=8, padx=5)
        self.cb_nac = ttk.Combobox(f_jog, values=NACIONALIDADES, width=18)
        self.cb_nac.grid(row=0, column=9, padx=5)
        self.cb_nac.bind("<KeyRelease>", self.autocompletar_add_nac)

        self.btn_add_jogador = ttk.Button(f_jog, text="Adicionar", command=self.add_jogador_no_time)
        self.btn_add_jogador.grid(row=0, column=10, padx=8)

        campos_add = [self.e_nome_jog, self.cb_pos, self.e_ovr, self.e_camisa, self.cb_nac, self.btn_add_jogador]

        def focus_next_add(event):
            cur = event.widget
            try:
                idx = campos_add.index(cur)
                next_idx = (idx + 1) % len(campos_add)
                campos_add[next_idx].focus_set()
            except:
                pass
            return "break"

        def focus_prev_add(event):
            cur = event.widget
            try:
                idx = campos_add.index(cur)
                prev_idx = (idx - 1) % len(campos_add)
                campos_add[prev_idx].focus_set()
            except:
                pass
            return "break"

        for w in campos_add:
            w.bind("<Tab>", focus_next_add)
            w.bind("<Shift-Tab>", focus_prev_add)

        self.btn_add_jogador.bind("<Return>", lambda e: self.add_jogador_no_time())
        self.btn_add_time.bind("<Return>", lambda e: self.add_time())

        # Busca de jogadores livres - só aparece quando "Jogadores Livres" está selecionado
        self.f_busca_livres = ttk.LabelFrame(right, text="Buscar Jogador Livre")
        self.e_buscar_livre = ttk.Entry(self.f_busca_livres, font=("Helvetica", 10))
        self.e_buscar_livre.pack(side="left", fill="x", expand=True, padx=8, pady=8)
        self.e_buscar_livre.bind("<KeyRelease>", lambda e: self.atualizar_jogadores_time())
        self.e_buscar_livre.bind("<Return>", lambda e: self.atualizar_jogadores_time())
        ttk.Button(self.f_busca_livres, text="Buscar", command=self.atualizar_jogadores_time).pack(side="left", padx=(0, 8), pady=8)
        # não empacotado ainda: só é exibido em selecionar_time() quando o time for TIME_LIVRES

        tree_frame_jog_time = ttk.Frame(right, padding=(10, 5, 10, 5))
        tree_frame_jog_time.pack(fill="both", expand=True)

        v_scroll_jog_time = ttk.Scrollbar(tree_frame_jog_time, orient="vertical")
        v_scroll_jog_time.pack(side="right", fill="y")
        h_scroll_jog_time = ttk.Scrollbar(tree_frame_jog_time, orient="horizontal")
        h_scroll_jog_time.pack(side="bottom", fill="x")

        cols_jog = ("Nome", "Camisa", "Posição", "Overall", "Nacionalidade")
        self.tree_jog_time = ttk.Treeview(tree_frame_jog_time, columns=cols_jog, show="headings",
                                          yscrollcommand=v_scroll_jog_time.set, xscrollcommand=h_scroll_jog_time.set, style="Treeview")
        v_scroll_jog_time.config(command=self.tree_jog_time.yview)
        h_scroll_jog_time.config(command=self.tree_jog_time.xview)

        for c in cols_jog:
            self.tree_jog_time.heading(c, text=c, command=lambda col=c: self.ordenar_jogadores_time(col))
            align = "center" if c != "Nome" else "w"
            self.tree_jog_time.column(c, anchor=align, minwidth=0, stretch=True)

        self.tree_jog_time.tag_configure("Titular", background="#cce5ff")
        self.tree_jog_time.tag_configure("Reserva", background="#ffeb99")
        self.tree_jog_time.tag_configure("Resto", background="white")
        self.tree_jog_time.tag_configure("atencao", foreground="red")

        col_widths = self.config.get("col_widths_jog_time", {})
        if col_widths:
            for col in cols_jog:
                w = col_widths.get(col)
                if w is not None:
                    self.tree_jog_time.column(col, width=w, minwidth=0, stretch=True)
        else:
            self.tree_jog_time.column("Nome", width=150, anchor="w", minwidth=0, stretch=True)
            self.tree_jog_time.column("Camisa", width=80, minwidth=0, stretch=True)
            self.tree_jog_time.column("Posição", width=100, minwidth=0, stretch=True)
            self.tree_jog_time.column("Overall", width=100, minwidth=0, stretch=True)
            self.tree_jog_time.column("Nacionalidade", width=150, minwidth=0, stretch=True)

        self.tree_jog_time.pack(fill="both", expand=True)

        btns_jog_time = ttk.Frame(right)
        btns_jog_time.pack(pady=8)
        self.btn_remover_jog_time = ttk.Button(btns_jog_time, text="Remover Jogador (Del)", command=self.remover_jogador_time)
        self.btn_remover_jog_time.pack(side="left", padx=6)

        # Eventos para tree_times (inclui drag/drop e seleção)
        self.tree_times.bind("<<TreeviewSelect>>", self.selecionar_time)
        self.tree_times.bind("<Up>", lambda e: self.navegar_times('prev'))
        self.tree_times.bind("<Down>", lambda e: self.navegar_times('next'))
        self.tree_times.bind("<Key>", self.buscar_time_por_digitacao)
        self.tree_times.bind("<Double-1>", self.duplo_clique_time)
        self.tree_times.bind("<Return>", self.duplo_clique_time)
        self.tree_times.bind("<Delete>", lambda e: self.excluir_time())
        self.tree_times.bind("<F2>", lambda e: self.renomear_time())
        self.tree_times.bind("<Button-1>", self.drag_start_time)
        self.tree_times.bind("<B1-Motion>", self.drag_move_time)
        self.tree_times.bind("<ButtonRelease-1>", self.drag_end_time)
        self.drag_time = None

        # menu de contexto próprio para tree_times (incluir "Adicionar Liga")
        self.tree_times_menu = tk.Menu(self.root, tearoff=0)
        self.tree_times_menu.add_command(label="Adicionar Time",  command=self.add_time)
        self.tree_times_menu.add_command(label="Adicionar Liga",  command=self.adicionar_liga_dialogo)
        self.tree_times_menu.add_command(label="Transferir Time", command=self.transferir_time_dialogo)
        self.tree_times_menu.add_separator()
        self.uniforme_menu = tk.Menu(self.tree_times_menu, tearoff=0)
        self.tree_times_menu.add_cascade(label="Uniforme", menu=self.uniforme_menu)
        self.editado_menu = tk.Menu(self.tree_times_menu, tearoff=0)
        self.tree_times_menu.add_cascade(label="Editado", menu=self.editado_menu)
        self.tree_times_menu.add_separator()
        # índice 7 — habilitado apenas para linhas de liga
        self.tree_times_menu.add_command(label="🏳  Atribuir Bandeira à Liga...",
                                         command=self._atribuir_bandeira_liga,
                                         state="disabled")
        self.tree_times_menu.add_separator()
        self.tree_times_menu.add_command(label="Editar Time", command=self.editar_time_dialogo)
        self.tree_times_menu.add_command(label="Renomear",    command=self.renomear_time)
        self.tree_times_menu.add_command(label="Excluir",     command=self.excluir_time)

        # botão direito exibe menu de times/ligas
        self.tree_times.bind("<Button-3>", self.exibir_menu_times)
        self.tree_times.bind("<Button-2>", lambda e: self.selecionar_por_clique_meio(e, self.tree_times))

        # ── bandeiras ────────────────────────────────────────────────────
        self.bandeiras_ligas: dict = self.config.get("bandeiras_ligas", {})

        self._ov_jog = OverlayBandeiras(
            self.root, self.tree_jog, col_nac="Nacionalidade")
        self._ov_jog_time = OverlayBandeiras(
            self.root, self.tree_jog_time, col_nac="Nacionalidade")
        self._ov_times = OverlayBandeiras(
            self.root, self.tree_times,
            col_liga="Time",
            get_img_liga=self._get_img_liga)

        # Sem isso, ao trocar de aba ou restaurar a janela minimizada, as
        # bandeiras só reapareceriam no próximo ciclo do loop de segurança
        # (até ~500ms depois) — aqui forçamos na hora.
        def _forcar_todos_overlays(_=None):
            for ov in (self._ov_jog, self._ov_jog_time, self._ov_times):
                ov.forcar()
        self.nb.bind("<<NotebookTabChanged>>", _forcar_todos_overlays, add="+")
        self.root.bind("<Map>", _forcar_todos_overlays, add="+")
        self.root.bind("<FocusIn>", _forcar_todos_overlays, add="+")

        # Baixar bandeiras em background (salva em disco na 1ª vez)
        self.root.after(600, lambda: carregar_bandeiras(self.root, self.atualizar_tudo))

        self.tree_times.bind("<Tab>", lambda e: self.proximo_foco(e, self.btn_renomear))
        self.tree_times.bind("<Shift-Tab>", lambda e: self.anterior_foco(e, self.e_novo_time))
        self.tree_times.bind("<End>", self.selecionar_ultimo_time)
        self.tree_times.bind("<Home>", self.selecionar_primeiro_time)

        self.tree_jog_time.bind("<Double-1>", self.duplo_clique_jogador_time)
        self.tree_jog_time.bind("<Return>", self.duplo_clique_jogador_time)
        self.tree_jog_time.bind("<Delete>", lambda e: self.remover_jogador_time())
        self.tree_jog_time.bind("<Button-3>", lambda e: self.exibir_menu_contexto(e, self.tree_jog_time))
        self.tree_jog_time.bind("<Button-2>", lambda e: self.selecionar_por_clique_meio(e, self.tree_jog_time))
        self.tree_jog_time.bind("<Key>", self.buscar_jogador_por_digitacao)
        self.tree_jog_time.bind("<End>", self.selecionar_ultimo_jogador)
        self.tree_jog_time.bind("<Home>", self.selecionar_primeiro_jogador)
        self.tree_jog_time.bind("<Button-1>", self.drag_start_jog_time)
        self.tree_jog_time.bind("<B1-Motion>", self.drag_move_jog_time)
        self.tree_jog_time.bind("<ButtonRelease-1>", self.drag_end_jog_time)
        self.drag_jog = None

        self.tree_jog_time.bind("<Tab>", lambda e: self.proximo_foco(e, self.btn_remover_jog_time))
        self.tree_jog_time.bind("<Shift-Tab>", lambda e: self.anterior_foco(e, self.e_nome_jog))

        # Drag de cabeçalho de coluna para reordenar colunas do tree_jog_time
        self._col_drag_source = None
        self.tree_jog_time.bind("<ButtonPress-1>", self._col_drag_start, add="+")
        self.tree_jog_time.bind("<ButtonRelease-1>", self._col_drag_end, add="+")

        self.atualizar_times()

    def obter_liga_do_time(self, nome_time):
        """Retorna o nome da liga à qual o time pertence.
        "Jogadores Livres" é sempre colocado ao final de ordem_original,
        então ele NÃO pertence à última liga que aparece antes dele — não
        tem liga nenhuma."""
        if nome_time == TIME_LIVRES:
            return None
        liga_atual = None
        for nome in self.ordem_original:
            if self.dados["times"].get(nome, {}).get("liga", False):
                liga_atual = nome
            if nome == nome_time:
                return liga_atual
        return None

    # Função para exibir menu de contexto ao clicar com botão direito na lista de times/ligas
    def exibir_menu_times(self, event):
        row = self.tree_times.identify_row(event.y)
        if row:
            self.tree_times.selection_set(row)
            self.tree_times.focus(row)

            nome = self.tree_times.item(row, "values")[1]
            self.uniforme_menu.delete(0, tk.END)
            self.editado_menu.delete(0, tk.END)

            if self.dados["times"].get(nome, {}).get("liga", False):
                self.uniforme_menu.add_command(label="Marcar Liga (Uniformes Editados)", command=lambda: self.marcar_uniforme_liga(nome, True))
                self.uniforme_menu.add_command(label="Desmarcar Liga",                   command=lambda: self.marcar_uniforme_liga(nome, False))
                self.editado_menu.add_command(label="Marcar Liga (Editados)", command=lambda: self.marcar_editado_liga(nome, True))
                self.editado_menu.add_command(label="Desmarcar Liga",        command=lambda: self.marcar_editado_liga(nome, False))
            elif nome != TIME_LIVRES:
                status = self.dados["times"][nome].get("uniforme_editado", False)
                label  = "Desmarcar Uniforme" if status else "Uniforme Editado"
                self.uniforme_menu.add_command(label=label, command=lambda: self.toggle_uniforme_time(nome))
                liga = self.obter_liga_do_time(nome)
                if liga:
                    self.uniforme_menu.add_separator()
                    self.uniforme_menu.add_command(label=f"Marcar Todos ({liga})",    command=lambda l=liga: self.marcar_uniforme_liga(l, True))
                    self.uniforme_menu.add_command(label=f"Desmarcar Todos ({liga})", command=lambda l=liga: self.marcar_uniforme_liga(l, False))

                status_ed = self.dados["times"][nome].get("editado", False)
                label_ed  = "Desmarcar Editado" if status_ed else "Marcar Editado"
                self.editado_menu.add_command(label=label_ed, command=lambda: self.toggle_editado_time(nome))
                if liga:
                    self.editado_menu.add_separator()
                    self.editado_menu.add_command(label=f"Marcar Todos ({liga})",    command=lambda l=liga: self.marcar_editado_liga(l, True))
                    self.editado_menu.add_command(label=f"Desmarcar Todos ({liga})", command=lambda l=liga: self.marcar_editado_liga(l, False))
            else:
                self.uniforme_menu.add_command(label="Não disponível para Livres", state="disabled")
                self.editado_menu.add_command(label="Não disponível para Livres", state="disabled")

            # habilitar "Atribuir Bandeira" apenas para linhas de liga (índice 7)
            eh_liga = self.dados["times"].get(nome, {}).get("liga", False)
            self.tree_times_menu.entryconfig(7, state="normal" if eh_liga else "disabled")

        self.tree_times_menu.post(event.x_root, event.y_root)

    # ── Métodos de bandeira ───────────────────────────────────────────────

    def _get_img_liga(self, nome_liga: str):
        cod = self.bandeiras_ligas.get(nome_liga, "")
        if not cod:
            return None
        return _cache_cod_rgba.get(cod) or _cache_cod.get(cod)

    def _atribuir_bandeira_liga(self):
        sel = self.tree_times.selection()
        if not sel:
            return
        nome = self.tree_times.item(sel[0], "values")[1]
        if not self.dados["times"].get(nome, {}).get("liga", False):
            messagebox.showinfo("Atenção", "Selecione uma liga para atribuir bandeira.")
            return
        self._abrir_seletor_bandeira(nome)

    def _abrir_seletor_bandeira(self, nome_liga: str):
        dlg = tk.Toplevel(self.root)
        dlg.title(f"Bandeira: {nome_liga}")
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.geometry("660x470")
        dlg.resizable(True, True)
        dlg.update_idletasks()
        dlg.geometry(f"+{self.root.winfo_rootx()+60}+{self.root.winfo_rooty()+60}")

        # busca
        fr_top = ttk.Frame(dlg, padding=6)
        fr_top.pack(fill="x")
        ttk.Label(fr_top, text="Buscar:").pack(side="left")
        var_busca = tk.StringVar()
        ttk.Entry(fr_top, textvariable=var_busca, width=28).pack(side="left", padx=6)
        ttk.Label(fr_top, text="← clique na bandeira desejada").pack(side="left")

        # grade com scroll
        fr_mid = ttk.Frame(dlg)
        fr_mid.pack(fill="both", expand=True, padx=6)
        vsb = ttk.Scrollbar(fr_mid, orient="vertical")
        vsb.pack(side="right", fill="y")
        cv = tk.Canvas(fr_mid, yscrollcommand=vsb.set, bg="#f0f0f0", highlightthickness=0)
        cv.pack(fill="both", expand=True)
        vsb.config(command=cv.yview)
        fr_in = ttk.Frame(cv)
        wid = cv.create_window((0, 0), window=fr_in, anchor="nw")
        cv.bind("<Configure>",  lambda e: cv.itemconfig(wid, width=e.width))

        def _rolar(event):
            cv.yview_scroll(int(-1*(event.delta/120)), "units")

        def _bind_scroll(widget):
            """Propaga o scroll a qualquer widget filho (botões incluídos)."""
            widget.bind("<MouseWheel>", _rolar)
            for child in widget.winfo_children():
                _bind_scroll(child)

        cv.bind("<MouseWheel>", _rolar)
        dlg.bind("<MouseWheel>", _rolar)   # captura quando cursor está fora da grade

        sel_cod = [self.bandeiras_ligas.get(nome_liga, "")]
        botoes: list = []

        def _destacar(cod):
            for btn, c in botoes:
                btn.configure(relief="sunken" if c == cod else "raised",
                              bg="#cce5ff"    if c == cod else "SystemButtonFace")

        def _selecionar(cod):
            sel_cod[0] = cod
            _destacar(cod)

        def _popular(filtro=""):
            for w in fr_in.winfo_children():
                w.destroy()
            botoes.clear()
            paises = sorted([(n, c) for n, c in CODIGOS_PAISES.items()
                             if filtro.lower() in n.lower()],
                            key=lambda x: x[0])
            ncols = 4
            for i, (nac, cod) in enumerate(paises):
                r, c = divmod(i, ncols)
                fr_c = tk.Frame(fr_in, width=150, height=44)
                fr_c.grid(row=r, column=c, padx=3, pady=3, sticky="nsew")
                fr_c.grid_propagate(False)
                img = _cache_nac.get(nac, _placeholder())
                btn = tk.Button(
                    fr_c, image=img, compound="left",
                    text=f"  {nac}", anchor="w",
                    relief="sunken" if cod == sel_cod[0] else "raised",
                    bg="#cce5ff"    if cod == sel_cod[0] else "SystemButtonFace",
                    command=lambda c2=cod: _selecionar(c2))
                btn.pack(fill="both", expand=True)
                botoes.append((btn, cod))
            fr_in.update_idletasks()
            cv.configure(scrollregion=cv.bbox("all"))
            # rebindar scroll em todos os botões recém-criados
            _bind_scroll(fr_in)

        var_busca.trace_add("write", lambda *_: _popular(var_busca.get()))
        fr_in.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        _popular()

        # rodapé
        fr_bot = ttk.Frame(dlg, padding=6)
        fr_bot.pack(fill="x")

        def _remover():
            sel_cod[0] = ""
            _destacar("")

        def _confirmar():
            if sel_cod[0]:
                self.bandeiras_ligas[nome_liga] = sel_cod[0]
            else:
                self.bandeiras_ligas.pop(nome_liga, None)
            salvar_config(self)
            if hasattr(self, "_ov_times"):
                self._ov_times.forcar()
            dlg.destroy()

        ttk.Button(fr_bot, text="Sem Bandeira", command=_remover).pack(side="left")
        ttk.Button(fr_bot, text="Cancelar",     command=dlg.destroy).pack(side="right", padx=4)
        ttk.Button(fr_bot, text="OK",           command=_confirmar).pack(side="right")

    def toggle_uniforme_time(self, nome):
        if nome in self.dados["times"]:
            status = self.dados["times"][nome].get("uniforme_editado", False)
            self.dados["times"][nome]["uniforme_editado"] = not status
            salvar_dados(self.dados, self.ordem_original)
            self.atualizar_times()

    def marcar_uniforme_liga(self, nome_liga, status):
        # Encontrar times que pertencem a esta liga na ordem_original
        encontrou_liga = False
        for nome in self.ordem_original:
            if nome == nome_liga:
                encontrou_liga = True
                continue
            if encontrou_liga:
                time_data = self.dados["times"].get(nome)
                if not time_data or time_data.get("liga", False) or nome == TIME_LIVRES:
                    break
                time_data["uniforme_editado"] = status
        
        salvar_dados(self.dados, self.ordem_original)
        self.atualizar_times()

    def toggle_editado_time(self, nome):
        if nome in self.dados["times"] and nome != TIME_LIVRES:
            status = self.dados["times"][nome].get("editado", False)
            self.dados["times"][nome]["editado"] = not status
            salvar_dados(self.dados, self.ordem_original)
            self.atualizar_times()

    def marcar_editado_liga(self, nome_liga, status):
        # Encontrar times que pertencem a esta liga na ordem_original e marcar/desmarcar como editado
        encontrou_liga = False
        for nome in self.ordem_original:
            if nome == nome_liga:
                encontrou_liga = True
                continue
            if encontrou_liga:
                time_data = self.dados["times"].get(nome)
                if not time_data or time_data.get("liga", False) or nome == TIME_LIVRES:
                    break
                time_data["editado"] = status

        salvar_dados(self.dados, self.ordem_original)
        self.atualizar_times()

    def ordenar_times_por_media(self):
        if self.times_ordenado_por == "media_desc":
            self.times_ordenado_por = "media_asc"
        elif self.times_ordenado_por == "media_asc":
            self.times_ordenado_por = None
        else:
            self.times_ordenado_por = "media_desc"
        self.atualizar_times()
        texto = "Média"
        if self.times_ordenado_por == "media_desc":
            texto += " ↓"
        elif self.times_ordenado_por == "media_asc":
            texto += " ↑"
        self.tree_times.heading("Média", text=texto)

    def navegar_times(self, direction):
        children = self.tree_times.get_children()
        if not children:
            return "break"
        cur = self.tree_times.focus()
        if not cur:
            first = children[0]
            self.tree_times.focus(first)
            self.tree_times.selection_set(first)
            self.tree_times.see(first)
        else:
            if direction == 'next':
                nxt = self.tree_times.next(cur)
                if nxt:
                    self.tree_times.focus(nxt)
                    self.tree_times.selection_set(nxt)
                    self.tree_times.see(nxt)
                else:
                    return "break"
            elif direction == 'prev':
                prv = self.tree_times.prev(cur)
                if prv:
                    self.tree_times.focus(prv)
                    self.tree_times.selection_set(prv)
                    self.tree_times.see(prv)
                else:
                    return "break"
        self.selecionar_time()
        self.tree_times.focus_set()
        return "break"

    def autocompletar_add_nac(self, e):
        if e.keysym in ["BackSpace", "Delete", "Left", "Right", "Up", "Down", "Tab", "Return"]:
            return

        typed = self.cb_nac.get()
        
        # Lógica de busca por letra: APENAS se o campo estiver vazio e uma letra for digitada.
        if not typed and e.char and len(e.char) == 1:
            char = e.char.lower()
            for i, nac in enumerate(NACIONALIDADES):
                if remover_acentos(nac).lower().startswith(char):
                    self.cb_nac.current(i)
                    return "break"

        # Lógica de autocompletar: se o campo não estiver vazio, autocompleta.
        if not typed:
            return

        typed_lower = remover_acentos(typed).lower()
        matches = [nac for nac in NACIONALIDADES if remover_acentos(nac).lower().startswith(typed_lower)]
        
        if matches:
            match = matches[0]
            self.cb_nac.set(match)
            self.cb_nac.selection_range(len(typed), tk.END)

    def add_jogador_no_time(self):
        if not self.time_selecionado:
            messagebox.showwarning("Erro", "Selecione um time!")
            return

        # Bloquear se a seleção for uma liga (time_selecionado não deve apontar para liga)
        if self.dados["times"].get(self.time_selecionado, {}).get("liga", False):
            messagebox.showwarning("Erro", "Selecione um time (não uma liga)!")
            return

        nome = self.e_nome_jog.get().strip()
        pos = self.cb_pos.get()
        ovr_str = self.e_ovr.get().strip()
        camisa_str = self.e_camisa.get().strip()
        nac = self.cb_nac.get().strip()

        # Validar se a nacionalidade está na lista oficial
        if nac and nac not in NACIONALIDADES:
            messagebox.showerror("Erro", f"A nacionalidade '{nac}' não é válida!")
            return

        if not all([nome, pos, ovr_str]):
            messagebox.showwarning("Erro", "Preencha nome, posição e overall!")
            return

        if pos not in POSICOES_BR:
            messagebox.showerror("Erro", "Posição inválida!")
            return
        if not ovr_str.isdigit() or not (0 <= int(ovr_str) <= 99):
            messagebox.showerror("Erro", "Overall: 0-99")
            return

        camisa = ""
        if camisa_str:
            if not camisa_str.isdigit() or not (1 <= int(camisa_str) <= 99):
                messagebox.showerror("Erro", "Camisa: 1-99")
                return
            if any(j.get("camisa", "") == camisa_str
                   for j in self.dados["times"][self.time_selecionado]["jogadores"]):
                messagebox.showerror("Erro", f"Nº {camisa_str} já usado neste time!")
                return
            camisa = camisa_str

        t = self.dados["times"][self.time_selecionado]
        novo_id = str(uuid.uuid4())
        t["jogadores"].append({
            "id": novo_id,
            "nome": nome,
            "posicao": pos,
            "overall": int(ovr_str),
            "camisa": camisa,
            "nacionalidade": nac,
            "posicoes_secundarias": [],
            "nome_completo": "",
            "verificar_camisa": False
        })
        t.setdefault("ordem", [])
        t["ordem"].append(novo_id)
        salvar_dados(self.dados, self.ordem_original)

        detalhes_criacao = f"Posição {pos}, Overall {ovr_str}"
        if camisa:
            detalhes_criacao += f", Camisa {camisa}"
        if nac:
            detalhes_criacao += f", Nacionalidade {nac}"
        self.registrar_historico("Criação", nome, self.time_selecionado, detalhes_criacao)

        self.e_nome_jog.delete(0, tk.END)
        self.cb_pos.set("")
        self.e_ovr.delete(0, tk.END)
        self.e_camisa.delete(0, tk.END)
        self.cb_nac.set("")
        self.e_nome_jog.focus_set()

        self.atualizar_tudo()
        
        # Selecionar o novo jogador e fazer scroll
        for item in self.tree_jog_time.get_children():
            if item == novo_id:
                self.tree_jog_time.selection_set(item)
                self.tree_jog_time.focus(item)
                self.tree_jog_time.see(item)
                break

        # Já abre a janela completa de edição do jogador recém-criado,
        # para preencher nome completo / link do Transfermarkt / posições secundárias
        # sem precisar procurar e reabrir o jogador depois.
        jogador_ref = next((j for j in t["jogadores"] if j["id"] == novo_id), None)
        if jogador_ref:
            abrir_janela_edicao(
                self.root, self, jogador_ref, self.time_selecionado,
                lambda: self.manter_selecao_jogador_time(novo_id)
            )

    def media_time(self, nome):
        js = self.dados["times"][nome]["jogadores"]
        return round(sum(j['overall'] for j in js)/len(js), 1) if js else 0.0

    def atualizar_times(self):
        time_atual = self.time_selecionado
        for i in self.tree_times.get_children():
            self.tree_times.delete(i)

        # preparar lista de times/ligas seguindo self.ordem_original
        times_lista = []
        
        # Filtro de busca de times
        termo_busca = ""
        if hasattr(self, 'e_buscar_time'):
            termo_busca = remover_acentos(self.e_buscar_time.get().lower())

        for nome in self.ordem_original:
            if nome in self.dados["times"]:
                # Se houver busca, filtrar apenas times (ligas e Jogadores Livres sempre aparecem se houver times correspondentes neles)
                # Mas para simplificar, vamos filtrar pelo nome do time
                if termo_busca:
                    if termo_busca in remover_acentos(nome.lower()):
                        times_lista.append((nome, self.dados["times"][nome]))
                    # Se for uma liga, ela só aparece se não houver busca ou se o nome dela bater
                    # (Decidi manter ligas ocultas se não baterem na busca para limpar a visualização)
                else:
                    times_lista.append((nome, self.dados["times"][nome]))

        # aplicar ordenação por média apenas para times (ligas ficam na ordem_original)
        if self.times_ordenado_por == "media_desc":
            # ordenar apenas blocos dos times que não são ligas
            # para simplicidade, vamos gerar uma lista ordenada por média e manter ligas na posição relativa
            # abordagem: extrair times não-liga, ordenar por média, depois reencaixar respeitando ligas posições
            times_sem_liga = [(n, d) for n, d in times_lista if not d.get("liga", False) and n != TIME_LIVRES]
            times_sem_liga.sort(key=lambda x: self.media_time(x[0]), reverse=True)
            # reconstruir mantendo ligas na mesma ordem em que aparecem originalmente:
            nova = []
            iterator = iter(times_sem_liga)
            for n, d in times_lista:
                if d.get("liga", False):
                    nova.append((n, d))
                else:
                    try:
                        nova.append(next(iterator))
                    except StopIteration:
                        nova.append((n, d))
            times_lista = nova
        elif self.times_ordenado_por == "media_asc":
            times_sem_liga = [(n, d) for n, d in times_lista if not d.get("liga", False) and n != TIME_LIVRES]
            times_sem_liga.sort(key=lambda x: self.media_time(x[0]))
            nova = []
            iterator = iter(times_sem_liga)
            for n, d in times_lista:
                if d.get("liga", False):
                    nova.append((n, d))
                else:
                    try:
                        nova.append(next(iterator))
                    except StopIteration:
                        nova.append((n, d))
            times_lista = nova
        # caso default, manter ordem_original

        # Filtrar ligas e TIME_LIVRES se a ordenação por média estiver ativa
        if self.times_ordenado_por:
            times_lista = [(n, d) for n, d in times_lista if not d.get("liga", False) and n != TIME_LIVRES]

        # atualizar rodapé com contagem de times reais
        times_reais = {k: v for k, v in self.dados["times"].items() if not v.get("liga", False) and k != TIME_LIVRES}
        total_reais = len(times_reais)
        editados = sum(1 for k, v in self.dados["times"].items() if not v.get("liga", False) and v.get("editado", False))
        porcentagem = (editados / total_reais * 100) if total_reais > 0 else 0
        self.lbl_rodape.config(text=f"Editados: {editados}/{total_reais} ({porcentagem:.0f}%)")

        # Mapear times para suas ligas para contagem
        contagem_ligas = {}
        liga_atual = None
        for n, d in times_lista:
            if d.get("liga", False):
                liga_atual = n
                contagem_ligas[liga_atual] = {"total": 0, "editados": 0}
            elif liga_atual:
                if n != TIME_LIVRES:
                    contagem_ligas[liga_atual]["total"] += 1
                    if d.get("editado", False):
                        contagem_ligas[liga_atual]["editados"] += 1

        iid_sel = None
        for nome, data in times_lista:
            if data.get("liga", False):
                # Liga: sem média; marcador especial
                media = ""
                tag_cor = "liga"
                
                # Obter estatísticas da liga
                stats = contagem_ligas.get(nome, {"total": 0, "editados": 0})
                # Colocar o contador na coluna "Jogadores" (qtd)
                qtd = f"{stats['editados']}/{stats['total']}"
                
                # Nome de exibição limpo (sem o contador que antes ficava no nome)
                nome_exibicao = nome
                
                iid = self.tree_times.insert("", "end", values=("", nome_exibicao, media, qtd), tags=(tag_cor,))
            else:
                # Agora exibimos média e quantidade para todos os times, exceto média para TIME_LIVRES
                qtd = len(data["jogadores"])
                if nome == TIME_LIVRES:
                    media = ""
                else:
                    media = f"{self.media_time(nome):.1f}"
                editado = data.get("editado", False) and nome != TIME_LIVRES
                tag_cor = "editado" if editado else "nao_editado"
                
                tags = [tag_cor]
                
                # Lógica de atenção para o time
                atencao = False
                if isinstance(qtd, int) and qtd <= 16:
                    atencao = True
                
                if nome != TIME_LIVRES:
                    for j in data["jogadores"]:
                        # Se precisa verificar camisa ou se a camisa está vazia
                        if j.get("verificar_camisa", False) or not str(j.get("camisa", "")).strip():
                            atencao = True
                            break
                
                if atencao:
                    tags.append("atencao_time")
                
                # Coluna de status para uniforme editado
                status_u = "✓" if data.get("uniforme_editado", False) else ""
                
                # inserir com coluna de status
                iid = self.tree_times.insert("", "end", values=(status_u, nome, media, qtd), tags=tuple(tags))
            if nome == time_atual:
                iid_sel = iid

        if iid_sel:
            self.tree_times.selection_set(iid_sel)
            self.tree_times.see(iid_sel)
            self.tree_times.focus(iid_sel)

        # Ativar/desativar botões dependendo da seleção atual (não selecionar botões se TIME_LIVRES)
        estado_renomear = "normal"
        estado_excluir = "normal"

        if self.time_selecionado == TIME_LIVRES:
            estado_renomear = "disabled"
            estado_excluir = "disabled"
        # manter renomear/excluir para ligas (permitido)
        self.btn_renomear.config(state=estado_renomear)
        self.btn_excluir.config(state=estado_excluir)

        # se seleção é liga, desabilitar adicionar jogador
        if self.time_selecionado and self.dados["times"].get(self.time_selecionado, {}).get("liga", False):
            self.btn_add_jogador.config(state="disabled")
        else:
            self.btn_add_jogador.config(state="normal")

        # A lista de times/ligas foi repopulada — força o overlay a redesenhar.
        if hasattr(self, "_ov_times"):
            self._ov_times.forcar()

    def ordenar_jogadores_time(self, col):
        # Lógica de 3 estados: Crescente -> Decrescente -> Padrão (None)
        # Estado 0: coluna_ordenada_time = None
        # Estado 1: coluna_ordenada_time = col, ordem_desc_time = False (Crescente)
        # Estado 2: coluna_ordenada_time = col, ordem_desc_time = True (Decrescente)
        
        if self.coluna_ordenada_time != col:
            # Primeiro clique na coluna: Crescente
            self.coluna_ordenada_time = col
            self.ordem_desc_time = False
        elif self.ordem_desc_time == False:
            # Segundo clique na mesma coluna: Decrescente
            self.ordem_desc_time = True
        else:
            # Terceiro clique na mesma coluna: Volta ao padrão
            self.coluna_ordenada_time = None
            self.ordem_desc_time = False
            
        self.atualizar_jogadores_time()

    def atualizar_jogadores_time(self):
        for i in self.tree_jog_time.get_children():
            self.tree_jog_time.delete(i)
        if not self.time_selecionado:
            if hasattr(self, "_ov_jog_time"):
                self._ov_jog_time.forcar()
            return

        # se seleção for liga: não mostrar jogadores
        if self.dados["times"].get(self.time_selecionado, {}).get("liga", False):
            if hasattr(self, "_ov_jog_time"):
                self._ov_jog_time.forcar()
            return

        t = self.dados["times"].get(self.time_selecionado, {"jogadores": [], "ordem": []})

        if self.coluna_ordenada_time:
            def get_sort_key(j):
                nome_norm = remover_acentos(j["nome"]).lower()
                pais_norm = remover_acentos(j.get("nacionalidade", "")).lower()
                if self.coluna_ordenada_time == "Nome":
                    return (nome_norm, -j["overall"]) if not self.ordem_desc_time else (nome_norm, j["overall"])
                elif self.coluna_ordenada_time == "Camisa":
                    c = j.get("camisa", "")
                    val_c = int(c) if c.isdigit() else 999
                    return (val_c, -j["overall"], nome_norm) if not self.ordem_desc_time else (val_c, j["overall"], nome_norm)
                elif self.coluna_ordenada_time == "Posição":
                    idx_p = POSICOES_LISTA.index(j["posicao"])
                    return (idx_p, -j["overall"], nome_norm) if not self.ordem_desc_time else (idx_p, j["overall"], nome_norm)
                elif self.coluna_ordenada_time == "Overall":
                    return (j["overall"], [-(ord(c)) for c in nome_norm])
                elif self.coluna_ordenada_time == "Nacionalidade":
                    return (pais_norm, -j["overall"], nome_norm) if not self.ordem_desc_time else (pais_norm, j["overall"], nome_norm)
                return ""
            jogadores_ordenados = sorted(t["jogadores"], key=get_sort_key, reverse=self.ordem_desc_time)
        elif self.time_selecionado == TIME_LIVRES:
            # Ordem padrão para Livres: Overall Decrescente, Nome Crescente
            jogadores_ordenados = sorted(t["jogadores"], key=lambda j: (-j["overall"], remover_acentos(j["nome"]).lower()))
        else:
            ordem = t.get("ordem", [])
            jogadores_map = {j["id"]: j for j in t["jogadores"]}
            jogadores_ordenados = []
            for jid in ordem:
                if jid in jogadores_map:
                    jogadores_ordenados.append(jogadores_map.pop(jid))
            jogadores_ordenados.extend(jogadores_map.values())

        # Filtro de busca de jogadores livres - aplicado independente de qual
        # critério de ordenação foi usado acima
        if self.time_selecionado == TIME_LIVRES and hasattr(self, "e_buscar_livre"):
            filtro_livre = remover_acentos(self.e_buscar_livre.get().strip()).lower()
            if filtro_livre:
                jogadores_ordenados = [
                    j for j in jogadores_ordenados
                    if filtro_livre in remover_acentos(j["nome"]).lower()
                ]

        # Obter a ordem atual das colunas para garantir que os valores correspondam aos cabeçalhos
        ordem_colunas = list(self.tree_jog_time["columns"])
        
        for idx, j in enumerate(jogadores_ordenados):
            camisa = j.get("camisa", "") or "—"
            
            # Mapear valores para as colunas atuais
            mapa_valores = {
                "Nome": j["nome"],
                "Camisa": camisa,
                "Posição": j["posicao"],
                "Overall": j["overall"],
                "Nacionalidade": j.get("nacionalidade", "")
            }
            valores_ordenados = [mapa_valores.get(col, "") for col in ordem_colunas]

            bg_tag = "Resto" if self.time_selecionado == TIME_LIVRES else ("Titular" if idx < 11 else "Reserva" if idx < 23 else "Resto")
            tags = [bg_tag]

            # Destaque em vermelho se precisar verificar camisa ou se estiver sem número (exceto Livres)
            if self.time_selecionado != TIME_LIVRES:
                if j.get("verificar_camisa", False) or not str(j.get("camisa", "")).strip():
                    tags.append("atencao")
            elif j.get("verificar_camisa", False):
                tags.append("atencao")

            iid = j["id"]
            self.tree_jog_time.insert("", "end", iid=iid,
                                      values=valores_ordenados,
                                      tags=tags)

        if hasattr(self, "_ov_jog_time"):
            self._ov_jog_time.forcar()

    def drag_start_time(self, e):
        row = self.tree_times.identify_row(e.y)
        if row:
            self.drag_time = row

    def drag_move_time(self, e):
        if not self.drag_time:
            return
        target = self.tree_times.identify_row(e.y)
        if target and target != self.drag_time:
            self.tree_times.selection_set(target)

    def drag_end_time(self, e):
        if not self.drag_time:
            return
        target = self.tree_times.identify_row(e.y)
        if not target or target == self.drag_time:
            self.drag_time = None
            return

        itens = list(self.tree_times.get_children())
        i1, i2 = itens.index(self.drag_time), itens.index(target)
        
        # Extrair os nomes reais
        nomes_reais = [self.tree_times.item(x, "values")[1].strip() for x in itens]
        
        movido = nomes_reais.pop(i1)
        nomes_reais.insert(i2, movido)

        # atualizar ordem_original de acordo com a nova ordem
        self.ordem_original = nomes_reais[:]
        salvar_dados(self.dados, self.ordem_original)

        self.times_ordenado_por = None
        self.atualizar_times()
        self.drag_time = None

    def drag_start_jog_time(self, e):
        if not self.time_selecionado:
            return
        # bloquear drag de jogadores se seleção for liga
        if self.dados["times"].get(self.time_selecionado, {}).get("liga", False):
            return
        self.drag_jog = self.tree_jog_time.identify_row(e.y)

    def drag_move_jog_time(self, e):
        if not self.drag_jog:
            return
        target = self.tree_jog_time.identify_row(e.y)
        if target and target != self.drag_jog:
            self.tree_jog_time.selection_set(target)

    def drag_end_jog_time(self, e):
        if not self.drag_jog or not self.time_selecionado:
            return
        target = self.tree_jog_time.identify_row(e.y)
        if not target or target == self.drag_jog:
            self.drag_jog = None
            return

        itens = list(self.tree_jog_time.get_children())
        i1, i2 = itens.index(self.drag_jog), itens.index(target)
        ordem_ids = itens[:]
        movido = ordem_ids.pop(i1)
        ordem_ids.insert(i2, movido)

        self.dados["times"][self.time_selecionado]["ordem"] = ordem_ids
        salvar_dados(self.dados, self.ordem_original)
        self.atualizar_jogadores_time()
        self.drag_jog = None

    def duplo_clique_time(self, e):
        sel = self.tree_times.selection()
        if not sel:
            return
        nome = self.tree_times.item(sel[0], "values")[1]
        # se for liga, abrir diálogo de renomear (toggle edit status não faz sentido)
        if self.dados["times"].get(nome, {}).get("liga", False):
            # abrir renomear
            self.renomear_time()
            return
        if nome == TIME_LIVRES:
            return
        status = self.dados["times"][nome].get("editado", False)
        self.dados["times"][nome]["editado"] = not status
        salvar_dados(self.dados, self.ordem_original)
        self.atualizar_times()
        self.selecionar_time()

    def duplo_clique_jogador_time(self, event=None):
        if not self.time_selecionado:
            return

        # não permitir abrir edição quando seleção é liga
        if self.dados["times"].get(self.time_selecionado, {}).get("liga", False):
            return

        item = self.tree_jog_time.focus()
        if not item:
            return

        jogador_id = item
        jogadores = self.dados["times"][self.time_selecionado]["jogadores"]
        jogador_ref = next((j for j in jogadores if j["id"] == jogador_id), None)
        if not jogador_ref:
            return

        abrir_janela_edicao(
            self.root, self, jogador_ref, self.time_selecionado,
            lambda: self.manter_selecao_jogador_time(jogador_id)
        )

    def manter_selecao_jogador_time(self, jogador_id):
        self.atualizar_tudo()
        for item_id in self.tree_jog_time.get_children():
            if item_id == jogador_id:
                self.tree_jog_time.selection_set(item_id)
                self.tree_jog_time.focus(item_id)
                self.tree_jog_time.see(item_id)
                break

    def remover_jogador_time(self):
        if not self.time_selecionado:
            messagebox.showwarning("Atenção", "Selecione um time primeiro!")
            return
        # bloquear se seleção for liga
        if self.dados["times"].get(self.time_selecionado, {}).get("liga", False):
            messagebox.showwarning("Atenção", "Selecione um time (não uma liga)!")
            return

        sel = self.tree_jog_time.selection()
        if not sel:
            messagebox.showwarning("Atenção", "Selecione um jogador para remover!")
            return

        item_id = sel[0]
        jogador_id = item_id

        v = self.tree_jog_time.item(jogador_id, "values")
        nome = v[0]

        if messagebox.askyesno("Remover", f"Remover {nome} do {self.time_selecionado}?"):
            t = self.dados["times"][self.time_selecionado]
            jogador = next((j for j in t["jogadores"] if j["id"] == jogador_id), None)
            if jogador:
                t["jogadores"].remove(jogador)
                try:
                    t["ordem"].remove(jogador_id)
                except ValueError:
                    pass

            salvar_dados(self.dados, self.ordem_original)
            self.registrar_historico("Remoção", nome, self.time_selecionado, "Jogador removido do time")
            self.atualizar_tudo()

    def add_time(self):
        nome_inicial = self.e_novo_time.get().strip()
        self.dialogo_novo_time(nome_inicial)

    def dialogo_novo_time(self, nome_inicial=""):
        win = tk.Toplevel(self.root)
        win.title("Adicionar Time")
        win.geometry("450x320")
        win.transient(self.root)
        win.grab_set()
        win.resizable(False, False)

        win.update_idletasks()
        x = (win.winfo_screenwidth() // 2) - (win.winfo_width() // 2)
        y = (win.winfo_screenheight() // 2) - (win.winfo_height() // 2)
        win.geometry(f"+{x}+{y}")

        frame = ttk.Frame(win, padding=20)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)

        ttk.Label(frame, text="Nome do Time:", font=("Helvetica", 10, "bold")).grid(row=0, column=0, sticky="n", pady=(0, 5))
        e_nome = ttk.Entry(frame, width=40, font=("Helvetica", 10), justify="center")
        e_nome.grid(row=1, column=0, sticky="n", pady=(0, 15))
        e_nome.insert(0, nome_inicial)

        ttk.Label(frame, text="Nacionalidade do Time:", font=("Helvetica", 10, "bold")).grid(row=2, column=0, sticky="n", pady=(0, 5))
        cb_nac = ttk.Combobox(frame, values=[""] + NACIONALIDADES, width=38, font=("Helvetica", 10), justify="center")
        cb_nac.grid(row=3, column=0, sticky="n", pady=(0, 15))

        ttk.Label(frame, text="Liga do Time:", font=("Helvetica", 10, "bold")).grid(row=4, column=0, sticky="n", pady=(0, 5))
        ligas_disponiveis = ["(Nenhuma)"] + [n for n in self.ordem_original if self.dados["times"].get(n, {}).get("liga", False)]
        cb_liga = ttk.Combobox(frame, values=ligas_disponiveis, width=38, font=("Helvetica", 10), justify="center")
        cb_liga.grid(row=5, column=0, sticky="n", pady=(0, 15))
        _habilitar_setas_combobox(cb_liga)
        cb_liga.set("(Nenhuma)")

        def autocompletar_nac(e):
            if e.keysym in ["BackSpace", "Delete", "Left", "Right", "Up", "Down", "Tab", "Return"]:
                return
            typed = cb_nac.get()
            if not typed:
                return
            typed_lower = remover_acentos(typed).lower()
            matches = [nac for nac in NACIONALIDADES if remover_acentos(nac).lower().startswith(typed_lower)]
            if matches:
                match = matches[0]
                cb_nac.set(match)
                cb_nac.selection_range(len(typed), tk.END)
        cb_nac.bind("<KeyRelease>", autocompletar_nac)

        def autocompletar_liga(e):
            if e.keysym in ["BackSpace", "Delete", "Left", "Right", "Up", "Down", "Tab", "Return"]:
                return
            typed = cb_liga.get()
            if not typed:
                return
            typed_lower = remover_acentos(typed).lower()
            matches = [liga for liga in ligas_disponiveis if remover_acentos(liga).lower().startswith(typed_lower)]
            if matches:
                match = matches[0]
                cb_liga.set(match)
                cb_liga.selection_range(len(typed), tk.END)
        cb_liga.bind("<KeyRelease>", autocompletar_liga)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=6, column=0, pady=(15, 0), sticky="n")

        def confirmar(event=None):
            nome = e_nome.get().strip()
            nac = cb_nac.get().strip()
            liga_escolhida = cb_liga.get().strip()

            if not nome:
                messagebox.showerror("Erro", "Digite o nome do time!", parent=win)
                return
            if nome == TIME_LIVRES:
                messagebox.showerror("Erro", "Nome reservado!", parent=win)
                return
            if any(t.lower() == nome.lower() for t in self.dados["times"]):
                messagebox.showerror("Erro", f"O time '{nome}' já está cadastrado!", parent=win)
                return
            if liga_escolhida and liga_escolhida not in ligas_disponiveis:
                messagebox.showerror("Erro", "Liga inválida! Selecione uma liga existente ou deixe em '(Nenhuma)'.", parent=win)
                return

            self.dados["times"][nome] = {"jogadores": [], "ordem": [], "editado": False, "nacionalidade": nac}

            if liga_escolhida and liga_escolhida != "(Nenhuma)":
                # Inserir logo após o último time já cadastrado na liga escolhida
                idx_liga = self.ordem_original.index(liga_escolhida)
                pos_inserir = idx_liga + 1
                for i in range(idx_liga + 1, len(self.ordem_original)):
                    item_nome = self.ordem_original[i]
                    if self.dados["times"].get(item_nome, {}).get("liga", False) or item_nome == TIME_LIVRES:
                        pos_inserir = i
                        break
                    pos_inserir = i + 1
                self.ordem_original.insert(pos_inserir, nome)
            else:
                if TIME_LIVRES in self.ordem_original:
                    idx_livres = self.ordem_original.index(TIME_LIVRES)
                    self.ordem_original.insert(idx_livres, nome)
                else:
                    self.ordem_original.append(nome)

            # Reordena tudo por nacionalidade/nome, já respeitando a liga escolhida
            self.reordenar_times_por_nacionalidade()
            salvar_dados(self.dados, self.ordem_original)
            self.e_novo_time.delete(0, tk.END)
            self.atualizar_times()

            # Selecionar o novo time automaticamente
            for item in self.tree_times.get_children():
                if self.tree_times.item(item, "values")[1] == nome:
                    self.tree_times.selection_set(item)
                    self.tree_times.focus(item)
                    self.tree_times.see(item)
                    self.selecionar_time()
                    break

            win.destroy()

        ttk.Button(btn_frame, text="Adicionar", command=confirmar).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancelar", command=win.destroy).pack(side="left", padx=5)

        win.bind("<Return>", confirmar)
        win.bind("<Escape>", lambda e: win.destroy())

        if nome_inicial:
            cb_nac.focus_set()
        else:
            e_nome.focus_set()

    def adicionar_liga_dialogo(self):
        nome = simpledialog.askstring("Adicionar Liga", "Nome da Liga:")
        if not nome:
            return
        nome = nome.strip()
        if not nome:
            return
        if nome in self.dados["times"]:
            messagebox.showerror("Erro", "Já existe um time ou liga com esse nome!")
            return
        # criar entrada de liga (flag 'liga': True)
        self.dados["times"][nome] = {"liga": True}
        self.ordem_original.append(nome)
        salvar_dados(self.dados, self.ordem_original)
        self.atualizar_times()
        
        # Selecionar a nova liga automaticamente
        for item in self.tree_times.get_children():
            val = self.tree_times.item(item, "values")[1]
            # Extrair nome real da liga (ignorando o contador)
            nome_real = val.split("  ")[0].strip() if "  " in val else val.strip()
            if nome_real == nome:
                self.tree_times.selection_set(item)
                self.tree_times.focus(item)
                self.tree_times.see(item)
                self.selecionar_time()
                break

    def transferir_time_dialogo(self):
        if not self.time_selecionado or self.time_selecionado == TIME_LIVRES:
            messagebox.showwarning("Atenção", "Selecione um time válido para transferir!")
            return
        
        if self.dados["times"].get(self.time_selecionado, {}).get("liga", False):
            messagebox.showwarning("Atenção", "Não é possível transferir uma liga!")
            return

        # Obter lista de ligas na ordem original
        ligas = [nome for nome in self.ordem_original if self.dados["times"].get(nome, {}).get("liga", False)]
        if not ligas:
            messagebox.showinfo("Informação", "Nenhuma liga cadastrada para transferência!")
            return

        # Criar janela de seleção
        win = tk.Toplevel(self.root)
        win.title("Transferir Time")
        win.geometry("300x400")
        win.transient(self.root)
        win.grab_set()

        # Centralizar janela
        win.update_idletasks()
        x = (win.winfo_screenwidth() // 2) - (win.winfo_width() // 2)
        y = (win.winfo_screenheight() // 2) - (win.winfo_height() // 2)
        win.geometry(f"+{x}+{y}")

        ttk.Label(win, text=f"Transferir '{self.time_selecionado}' para:", font=("Helvetica", 10, "bold")).pack(pady=10)

        frame_lista = ttk.Frame(win)
        frame_lista.pack(fill="both", expand=True, padx=10, pady=5)

        scrollbar = ttk.Scrollbar(frame_lista)
        scrollbar.pack(side="right", fill="y")

        lb = tk.Listbox(frame_lista, yscrollcommand=scrollbar.set, font=("Helvetica", 10))
        lb.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=lb.yview)

        # Inserir ligas na ordem original
        for liga in ligas:
            lb.insert(tk.END, liga)

        # Lógica de busca por teclado no Listbox
        win.search_buffer = ""
        
        def buscar_na_lista(event):
            if not event.char or len(event.char) != 1:
                return
            
            char = event.char.lower()
            items = lb.get(0, tk.END)
            if not items:
                return
            
            current_sel = lb.curselection()
            start_idx = (current_sel[0] + 1) if current_sel else 0
            
            if char != win.search_buffer:
                win.search_buffer = char
                start_idx = 0
            
            char_sem_acento = remover_acentos(char)
            
            for i in range(len(items)):
                idx = (start_idx + i) % len(items)
                item_text = remover_acentos(items[idx]).lower()
                if item_text.startswith(char_sem_acento):
                    lb.selection_clear(0, tk.END)
                    lb.selection_set(idx)
                    lb.activate(idx)
                    lb.see(idx)
                    break

        lb.bind("<Key>", buscar_na_lista)
        lb.bind("<Double-1>", lambda e: confirmar())
        lb.bind("<Return>", lambda e: confirmar())
        lb.focus_set()

        def confirmar():
            sel = lb.curselection()
            if not sel:
                messagebox.showwarning("Atenção", "Selecione uma liga de destino!")
                return
            
            liga_destino = lb.get(sel[0])
            self.executar_transferencia_time(self.time_selecionado, liga_destino)
            win.destroy()

        btn_frame = ttk.Frame(win)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="Confirmar", command=confirmar).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancelar", command=win.destroy).pack(side="left", padx=5)

    def executar_transferencia_time(self, time_nome, liga_destino):
        if time_nome in self.ordem_original:
            self.ordem_original.remove(time_nome)
        
        try:
            idx_liga = self.ordem_original.index(liga_destino)
            pos_insercao = idx_liga + 1
            times_na_liga = []
            
            for i in range(idx_liga + 1, len(self.ordem_original)):
                item = self.ordem_original[i]
                if self.dados["times"].get(item, {}).get("liga", False):
                    break
                times_na_liga.append(item)
            
            times_na_liga.append(time_nome)
            times_na_liga.sort(key=lambda x: remover_acentos(x))
            
            count_remover = len(times_na_liga) - 1
            for _ in range(count_remover):
                if idx_liga + 1 < len(self.ordem_original):
                    self.ordem_original.pop(idx_liga + 1)
            
            for i, t in enumerate(times_na_liga):
                self.ordem_original.insert(idx_liga + 1 + i, t)
                
        except ValueError:
            self.ordem_original.append(time_nome)

        salvar_dados(self.dados, self.ordem_original)
        self.atualizar_times()
        messagebox.showinfo("Sucesso", f"Time '{time_nome}' transferido para '{liga_destino}' com sucesso!")

    def selecionar_ultimo_time(self, event=None):
        items = self.tree_times.get_children()
        if items:
            ultimo_item = items[-1]
            self.tree_times.selection_set(ultimo_item)
            self.tree_times.focus(ultimo_item)
            self.tree_times.see(ultimo_item)
            self.selecionar_time()
        return "break"

    def selecionar_primeiro_time(self, event=None):
        items = self.tree_times.get_children()
        if items:
            primeiro_item = items[0]
            self.tree_times.selection_set(primeiro_item)
            self.tree_times.focus(primeiro_item)
            self.tree_times.see(primeiro_item)
            self.selecionar_time()
        return "break"

    def _col_drag_start(self, event):
        """Detecta o início do arraste de um cabeçalho de coluna no tree_jog_time."""
        region = self.tree_jog_time.identify_region(event.x, event.y)
        if region == "heading":
            col_id = self.tree_jog_time.identify_column(event.x)
            # Converter #1, #2... para o nome real da coluna
            try:
                col_index = int(col_id.replace("#", "")) - 1
                cols = list(self.tree_jog_time["columns"])
                if 0 <= col_index < len(cols):
                    self._col_drag_source = cols[col_index]
                else:
                    self._col_drag_source = None
            except (ValueError, IndexError):
                self._col_drag_source = None
        else:
            self._col_drag_source = None

    def _col_drag_end(self, event):
        """Finaliza o arraste de cabeçalho de coluna e reordena se necessário."""
        if not self._col_drag_source:
            return
        region = self.tree_jog_time.identify_region(event.x, event.y)
        if region == "heading":
            col_id = self.tree_jog_time.identify_column(event.x)
            try:
                col_index = int(col_id.replace("#", "")) - 1
                cols = list(self.tree_jog_time["columns"])
                if 0 <= col_index < len(cols):
                    col_destino = cols[col_index]
                    if col_destino != self._col_drag_source:
                        # Salvar as larguras atuais antes de reconfigurar
                        larguras = {c: self.tree_jog_time.column(c, 'width') for c in cols}
                        
                        # Reordenar colunas
                        cols.remove(self._col_drag_source)
                        idx_destino = cols.index(col_destino)
                        cols.insert(idx_destino, self._col_drag_source)
                        
                        # Aplicar nova ordem e restaurar larguras e alinhamentos
                        self.tree_jog_time.configure(columns=cols)
                        for c in cols:
                            self.tree_jog_time.heading(c, text=c, command=lambda col=c: self.ordenar_jogadores_time(col))
                            align = "center" if c != "Nome" else "w"
                            self.tree_jog_time.column(c, width=larguras[c], anchor=align)
                        
                        # FORÇAR ATUALIZAÇÃO IMEDIATA DOS DADOS
                        self.atualizar_jogadores_time()
                        
            except (ValueError, IndexError):
                pass
        self._col_drag_source = None

    def selecionar_ultimo_jogador(self, event=None):
        items = self.tree_jog_time.get_children()
        if items:
            ultimo_item = items[-1]
            self.tree_jog_time.selection_set(ultimo_item)
            self.tree_jog_time.focus(ultimo_item)
            self.tree_jog_time.see(ultimo_item)
        return "break"

    def selecionar_primeiro_jogador(self, event=None):
        items = self.tree_jog_time.get_children()
        if items:
            primeiro_item = items[0]
            self.tree_jog_time.selection_set(primeiro_item)
            self.tree_jog_time.focus(primeiro_item)
            self.tree_jog_time.see(primeiro_item)
        return "break"

    def selecionar_ultimo_jogador_geral(self, event=None):
        items = self.tree_jog.get_children()
        if items:
            ultimo_item = items[-1]
            self.tree_jog.selection_set(ultimo_item)
            self.tree_jog.focus(ultimo_item)
            self.tree_jog.see(ultimo_item)
        return "break"

    def selecionar_primeiro_jogador_geral(self, event=None):
        items = self.tree_jog.get_children()
        if items:
            primeiro_item = items[0]
            self.tree_jog.selection_set(primeiro_item)
            self.tree_jog.focus(primeiro_item)
            self.tree_jog.see(primeiro_item)
        return "break"

    def buscar_jogador_por_digitacao(self, event):
        # Ignorar teclas de controle
        if len(event.char) != 1 or event.keysym in ('Up', 'Down', 'Left', 'Right', 'Shift_L', 'Shift_R', 'Control_L', 'Control_R', 'Alt_L', 'Alt_R', 'Tab', 'Return', 'Escape', 'Home', 'End'):
            return

        char = event.char.lower()
        current_focus = self.tree_jog_time.focus()
        children = self.tree_jog_time.get_children()
        
        if not children: return "break"

        # Começar a busca a partir do item selecionado
        start_index = children.index(current_focus) if current_focus in children else -1
        
        # Se for a mesma tecla, busca o PRÓXIMO. Se for nova, busca a partir do atual.
        if char == self.jogador_search_buffer:
            start_search_at = (start_index + 1) % len(children)
        else:
            self.jogador_search_buffer = char
            start_search_at = start_index if start_index != -1 else 0

        buffer_sem_acento = remover_acentos(char)
        
        for i in range(len(children)):
            idx = (start_search_at + i) % len(children)
            item_id = children[idx]
            nome_jogador = self.tree_jog_time.item(item_id, "values")[0]
            nome_sem_acento = remover_acentos(nome_jogador).lower()
            
            if nome_sem_acento.startswith(buffer_sem_acento):
                # Se for a mesma tecla e cair no mesmo item, pula para o próximo se possível
                if char == self.jogador_search_buffer and item_id == current_focus and len(children) > 1 and i == 0:
                    continue
                self.tree_jog_time.selection_set(item_id)
                self.tree_jog_time.focus(item_id)
                self.tree_jog_time.see(item_id)
                break

        if self.jogador_search_timer: self.root.after_cancel(self.jogador_search_timer)
        self.jogador_search_timer = self.root.after(1000, lambda: self.limpar_buffer_jogador())
        return "break"

    def limpar_buffer_jogador(self):
        self.jogador_search_buffer = ""
        self.jogador_search_timer = None

    def buscar_time_por_digitacao(self, event):
        # Ignorar teclas de controle
        if len(event.char) != 1 or event.keysym in ('Up', 'Down', 'Left', 'Right', 'Shift_L', 'Shift_R', 'Control_L', 'Control_R', 'Alt_L', 'Tab', 'Return', 'Escape', 'Home', 'End'):
            return

        char = event.char.lower()
        current_focus = self.tree_times.focus()
        children = self.tree_times.get_children()
        
        if not children: return "break"

        # Começar a busca a partir do item selecionado
        start_index = children.index(current_focus) if current_focus in children else -1
        
        # Se for a mesma tecla, busca o PRÓXIMO. Se for nova, busca a partir do atual.
        if char == self.time_search_buffer:
            start_search_at = (start_index + 1) % len(children)
        else:
            self.time_search_buffer = char
            start_search_at = start_index if start_index != -1 else 0

        buffer_sem_acento = remover_acentos(char)
        
        for i in range(len(children)):
            idx = (start_search_at + i) % len(children)
            item_id = children[idx]
            nome_time = self.tree_times.item(item_id, "values")[1]
            nome_sem_acento = remover_acentos(nome_time).lower()
            
            if nome_sem_acento.startswith(buffer_sem_acento):
                # Se for a mesma tecla e cair no mesmo item, pula para o próximo se possível
                if char == self.time_search_buffer and item_id == current_focus and len(children) > 1 and i == 0:
                    continue
                self.tree_times.selection_set(item_id)
                self.tree_times.focus(item_id)
                self.tree_times.see(item_id)
                self.selecionar_time()
                break

        if self.time_search_timer: self.root.after_cancel(self.time_search_timer)
        self.time_search_timer = self.root.after(1000, lambda: self.limpar_buffer_time())
        return "break"

    def limpar_buffer_time(self):
        self.time_search_buffer = ""
        self.time_search_timer = None

    def selecionar_time(self, e=None):
        sel_item = self.tree_times.focus() or (self.tree_times.selection()[0] if self.tree_times.selection() else None)
        if sel_item:
            time_nome = self.tree_times.item(sel_item, "values")[1]

            # se seleção mudou:
            if time_nome != self.time_selecionado:
                self.time_selecionado = time_nome

                # SEMPRE voltar para a ordem padrão ao trocar de time
                padrao = ("Nome", "Camisa", "Posição", "Overall", "Nacionalidade")
                
                # Salvar as larguras atuais para não perdê-las ao resetar para o padrão
                cols_atuais = list(self.tree_jog_time["columns"])
                larguras = {c: self.tree_jog_time.column(c, 'width') for c in cols_atuais}
                
                self.tree_jog_time.configure(columns=padrao)
                for c in padrao:
                    self.tree_jog_time.heading(c, text=c, command=lambda col=c: self.ordenar_jogadores_time(col))
                    align = "center" if c != "Nome" else "w"
                    # Se a coluna já existia, mantém a largura dela; senão usa padrão
                    largura = larguras.get(c, 150 if c == "Nome" else 100)
                    self.tree_jog_time.column(c, width=largura, anchor=align)

                # se for liga, indicar que é liga e não exibir jogadores
                if self.dados["times"].get(time_nome, {}).get("liga", False):
                    self.lbl_time.config(text=f"Liga: {time_nome}")
                else:
                    self.lbl_time.config(text=time_nome)
                self.atualizar_jogadores_time()

                # estado de botões - permitir renomear/excluir para ligas, mas desabilitar adicionar jogador
                estado = "disabled" if time_nome == TIME_LIVRES else "normal"
                # renomear/excluir ficam habilitados para ligas (permitido), exceto TIME_LIVRES
                if time_nome == TIME_LIVRES:
                    self.btn_renomear.config(state="disabled")
                    self.btn_excluir.config(state="disabled")
                else:
                    self.btn_renomear.config(state="normal")
                    self.btn_excluir.config(state="normal")

                # se for liga, desabilitar adicionar jogador
                if self.dados["times"].get(time_nome, {}).get("liga", False):
                    self.btn_add_jogador.config(state="disabled")
                else:
                    self.btn_add_jogador.config(state="normal")

                # mostrar a busca de jogadores livres apenas para o time "Jogadores Livres"
                if time_nome == TIME_LIVRES:
                    self.f_busca_livres.pack(fill="x", padx=10, pady=(0, 5), before=self.tree_jog_time.master)
                else:
                    self.f_busca_livres.pack_forget()
                    self.e_buscar_livre.delete(0, tk.END)
        else:
            self.time_selecionado = None
            self.lbl_time.config(text="Selecione um time")
            self.atualizar_jogadores_time()

    def editar_time_dialogo(self):
        sel = self.tree_times.selection()
        if not sel:
            return
        nome = self.tree_times.item(sel[0], "values")[1]
            
        if nome == TIME_LIVRES:
            return
        
        # Não permitir editar ligas
        if self.dados["times"].get(nome, {}).get("liga", False):
            messagebox.showwarning("Atenção", "Não é possível editar uma liga. Use 'Renomear' para alterar o nome.")
            return
        
        # Criar janela de edição
        win = tk.Toplevel(self.root)
        win.title("Editar Time")
        win.geometry("450x320")
        win.transient(self.root)
        win.grab_set()
        win.resizable(False, False)
        
        # Centralizar janela
        win.update_idletasks()
        x = (win.winfo_screenwidth() // 2) - (win.winfo_width() // 2)
        y = (win.winfo_screenheight() // 2) - (win.winfo_height() // 2)
        win.geometry(f"+{x}+{y}")
        
        frame = ttk.Frame(win, padding=20)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        
        # Nome do time
        ttk.Label(frame, text="Nome do Time:", font=("Helvetica", 10, "bold")).grid(row=0, column=0, sticky="n", pady=(0, 5))
        e_nome = ttk.Entry(frame, width=40, font=("Helvetica", 10), justify="center")
        e_nome.grid(row=1, column=0, sticky="n", pady=(0, 15))
        e_nome.insert(0, nome)
        
        # Nacionalidade do time
        ttk.Label(frame, text="Nacionalidade do Time:", font=("Helvetica", 10, "bold")).grid(row=2, column=0, sticky="n", pady=(0, 5))
        cb_nac = ttk.Combobox(frame, values=[""] + NACIONALIDADES, width=38, font=("Helvetica", 10), justify="center")
        cb_nac.grid(row=3, column=0, sticky="n", pady=(0, 15))
        cb_nac.set(self.dados["times"][nome].get("nacionalidade", ""))
        
        # Liga do time
        ttk.Label(frame, text="Liga do Time:", font=("Helvetica", 10, "bold")).grid(row=4, column=0, sticky="n", pady=(0, 5))
        ligas_disponiveis = ["(Nenhuma)"] + [n for n in self.ordem_original if self.dados["times"].get(n, {}).get("liga", False)]
        cb_liga = ttk.Combobox(frame, values=ligas_disponiveis, width=38, font=("Helvetica", 10), justify="center")
        cb_liga.grid(row=5, column=0, sticky="n", pady=(0, 15))
        _habilitar_setas_combobox(cb_liga)
        
        # Iniciar a liga em branco conforme solicitado
        cb_liga.set("")
        
        # Autocompletar nacionalidade
        def autocompletar_nac(e):
            if e.keysym in ["BackSpace", "Delete", "Left", "Right", "Up", "Down", "Tab", "Return"]:
                return
            
            typed = cb_nac.get()
            if not typed:
                return
            
            typed_lower = remover_acentos(typed).lower()
            matches = [nac for nac in NACIONALIDADES if remover_acentos(nac).lower().startswith(typed_lower)]
            if matches:
                match = matches[0]
                cb_nac.set(match)
                cb_nac.selection_range(len(typed), tk.END)
                
        cb_nac.bind("<KeyRelease>", autocompletar_nac)

        # Autocompletar liga (agora digitável, igual à nacionalidade)
        def autocompletar_liga(e):
            if e.keysym in ["BackSpace", "Delete", "Left", "Right", "Up", "Down", "Tab", "Return"]:
                return
            
            typed = cb_liga.get()
            if not typed:
                return
            
            typed_lower = remover_acentos(typed).lower()
            matches = [liga for liga in ligas_disponiveis if remover_acentos(liga).lower().startswith(typed_lower)]
            if matches:
                match = matches[0]
                cb_liga.set(match)
                cb_liga.selection_range(len(typed), tk.END)
                
        cb_liga.bind("<KeyRelease>", autocompletar_liga)
        
        # Botões
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=6, column=0, pady=(15, 0), sticky="n")
        
        def salvar(event=None):
            novo_nome = e_nome.get().strip()
            nova_nac = cb_nac.get().strip()
            nova_liga = cb_liga.get()
            
            if not novo_nome:
                messagebox.showerror("Erro", "Nome não pode estar vazio!", parent=win)
                return
            
            if novo_nome == TIME_LIVRES:
                messagebox.showerror("Erro", "Nome reservado!", parent=win)
                return
            
            # Verificar se o nome já existe (exceto se for o mesmo time)
            if novo_nome != nome and novo_nome in self.dados["times"]:
                messagebox.showerror("Erro", "Nome já usado!", parent=win)
                return
            
            # Validar a liga digitada (agora que o campo é digitável, não só um dropdown)
            if nova_liga not in ("",) and nova_liga not in ligas_disponiveis:
                messagebox.showerror("Erro", "Liga inválida! Selecione uma liga existente ou deixe em branco.", parent=win)
                return
            
            # Atualizar dados
            time_data = self.dados["times"][nome]
            
            # Se o nome mudou, renomear
            if novo_nome != nome:
                self.dados["times"][novo_nome] = self.dados["times"].pop(nome)
                if nome in self.ordem_original:
                    idx = self.ordem_original.index(nome)
                    self.ordem_original[idx] = novo_nome
                if self.time_selecionado == nome:
                    self.time_selecionado = novo_nome
                time_data = self.dados["times"][novo_nome]
            
            # Atualizar nacionalidade
            nacionalidade_antiga = time_data.get("nacionalidade", "")
            time_data["nacionalidade"] = nova_nac
            
            # Mudar de liga se necessário
            liga_anterior = self.obter_liga_do_time(novo_nome)
            # Se estiver em branco, mantém a liga atual (não altera)
            if nova_liga == "":
                nova_liga = liga_anterior
            elif nova_liga == "(Nenhuma)":
                nova_liga = None
                
            if nova_liga != liga_anterior:
                # Remover da posição atual
                if novo_nome in self.ordem_original:
                    self.ordem_original.remove(novo_nome)
                
                if nova_liga is None:
                    # Se for sem liga, vai para o final ou antes do TIME_LIVRES
                    if TIME_LIVRES in self.ordem_original:
                        idx_livres = self.ordem_original.index(TIME_LIVRES)
                        self.ordem_original.insert(idx_livres, novo_nome)
                    else:
                        self.ordem_original.append(novo_nome)
                else:
                    # Inserir após a nova liga
                    if nova_liga in self.ordem_original:
                        idx_liga = self.ordem_original.index(nova_liga)
                        # Encontrar o fim da liga (próxima liga ou fim da lista)
                        pos_inserir = idx_liga + 1
                        for i in range(idx_liga + 1, len(self.ordem_original)):
                            item_nome = self.ordem_original[i]
                            if self.dados["times"].get(item_nome, {}).get("liga", False) or item_nome == TIME_LIVRES:
                                pos_inserir = i
                                break
                            pos_inserir = i + 1
                        self.ordem_original.insert(pos_inserir, novo_nome)
            
            # Sempre reordenar para garantir a ordem alfabética de país e nome
            self.reordenar_times_por_nacionalidade()
            
            salvar_dados(self.dados, self.ordem_original)
            self.atualizar_tudo()
            win.destroy()
        
        ttk.Button(btn_frame, text="Salvar", command=salvar).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancelar", command=win.destroy).pack(side="left", padx=5)
        
        e_nome.focus_set()
        # Vincular Enter em toda a janela para salvar
        win.bind("<Return>", salvar)
        # Vincular Esc para cancelar
        win.bind("<Escape>", lambda e: win.destroy())

    def reordenar_times_por_nacionalidade(self):
        """
        Reordena os times na ordem_original agrupando por nacionalidade
        e ordenando alfabeticamente dentro de cada grupo.
        Times dentro de ligas são ordenados dentro da própria liga.
        Times sem liga são ordenados globalmente.
        """
        # Identificar estrutura de ligas
        estrutura = []  # [(tipo, nome, [times_da_liga])]
        liga_atual = None
        times_da_liga_atual = []
        times_sem_liga = []
        
        for nome in self.ordem_original:
            time_data = self.dados["times"].get(nome)
            if not time_data:
                continue
            
            if time_data.get("liga", False):
                # Salvar liga anterior se existir
                if liga_atual is not None:
                    estrutura.append(("liga", liga_atual, times_da_liga_atual[:]))
                # Iniciar nova liga
                liga_atual = nome
                times_da_liga_atual = []
            elif nome == TIME_LIVRES:
                # Salvar liga anterior se existir
                if liga_atual is not None:
                    estrutura.append(("liga", liga_atual, times_da_liga_atual[:]))
                    liga_atual = None
                    times_da_liga_atual = []
                # Adicionar TIME_LIVRES como especial
                estrutura.append(("especial", nome, []))
            else:
                # Time normal
                if liga_atual is not None:
                    times_da_liga_atual.append(nome)
                else:
                    times_sem_liga.append(nome)
        
        # Salvar última liga se existir
        if liga_atual is not None:
            estrutura.append(("liga", liga_atual, times_da_liga_atual[:]))
        
        # Ordenar times dentro de cada liga por nacionalidade e nome
        for i, (tipo, nome, times) in enumerate(estrutura):
            if tipo == "liga" and times:
                times_com_nac = []
                times_sem_nac = []
                
                for time_nome in times:
                    time_data = self.dados["times"].get(time_nome)
                    if time_data:
                        nac = time_data.get("nacionalidade", "").strip()
                        if nac:
                            times_com_nac.append((nac, time_nome))
                        else:
                            times_sem_nac.append(time_nome)
                
                # Ordenar por nacionalidade e depois por nome
                times_com_nac.sort(key=lambda x: (remover_acentos(x[0]), remover_acentos(x[1])))
                times_sem_nac.sort(key=lambda x: remover_acentos(x))
                
                # Reconstruir lista de times da liga
                times_ordenados = [nome for _, nome in times_com_nac] + times_sem_nac
                estrutura[i] = (tipo, nome, times_ordenados)
        
        # Ordenar times sem liga por nacionalidade e nome
        times_sem_liga_com_nac = []
        times_sem_liga_sem_nac = []
        
        for time_nome in times_sem_liga:
            time_data = self.dados["times"].get(time_nome)
            if time_data:
                nac = time_data.get("nacionalidade", "").strip()
                if nac:
                    times_sem_liga_com_nac.append((nac, time_nome))
                else:
                    times_sem_liga_sem_nac.append(time_nome)
        
        times_sem_liga_com_nac.sort(key=lambda x: (remover_acentos(x[0]), remover_acentos(x[1])))
        times_sem_liga_sem_nac.sort(key=lambda x: remover_acentos(x))
        
        # Reconstruir ordem_original
        nova_ordem = []
        
        # Adicionar times sem liga primeiro
        for _, nome in times_sem_liga_com_nac:
            nova_ordem.append(nome)
        for nome in times_sem_liga_sem_nac:
            nova_ordem.append(nome)
        
        # Adicionar ligas e seus times
        for tipo, nome, times in estrutura:
            nova_ordem.append(nome)
            nova_ordem.extend(times)
        
        self.ordem_original = nova_ordem

    def renomear_time(self):
        sel = self.tree_times.selection()
        if not sel:
            return
        antigo = self.tree_times.item(sel[0], "values")[1]
            
        if antigo == TIME_LIVRES:
            return
        novo = simpledialog.askstring("Renomear", "Novo nome:", initialvalue=antigo)
        if novo and novo.strip() and novo.strip() != antigo:
            novo = novo.strip()
            if novo == TIME_LIVRES:
                messagebox.showerror("Erro", "Nome reservado!")
                return
            if novo in self.dados["times"]:
                messagebox.showerror("Erro", "Nome já usado!")
                return
            # mover a entrada no dicionário mantendo seus dados (se liga, manter flag)
            self.dados["times"][novo] = self.dados["times"].pop(antigo)
            # atualizar ordem_original
            if antigo in self.ordem_original:
                idx = self.ordem_original.index(antigo)
                self.ordem_original[idx] = novo
            salvar_dados(self.dados, self.ordem_original)
            if self.time_selecionado == antigo:
                self.time_selecionado = novo
            self.atualizar_tudo()

    def excluir_time(self):
        sel = self.tree_times.selection()
        if not sel:
            return
        nome = self.tree_times.item(sel[0], "values")[1]
            
        if nome == TIME_LIVRES:
            return
        # confirmação diferente se for liga: excluir liga não exclui jogadores (porque liga não tem jogadores)
        if self.dados["times"].get(nome, {}).get("liga", False):
            if messagebox.askyesno("Excluir Liga", f"Excluir a liga '{nome}'? (Isto removerá apenas o separador de liga.)"):
                del self.dados["times"][nome]
                if nome in self.ordem_original:
                    self.ordem_original.remove(nome)
                salvar_dados(self.dados, self.ordem_original)
                self.time_selecionado = None
                self.atualizar_tudo()
        else:
            if messagebox.askyesno("Excluir", f"Excluir {nome} e todos os jogadores?"):
                del self.dados["times"][nome]
                if nome in self.ordem_original:
                    self.ordem_original.remove(nome)
                salvar_dados(self.dados, self.ordem_original)
                self.time_selecionado = None
                self.atualizar_tudo()

    def montar_anotacoes(self):
        f_anotacoes = ttk.Frame(self.pagina_anotacoes, padding=10)
        f_anotacoes.pack(fill="both", expand=True)

        self.txt_anotacoes = tk.Text(f_anotacoes, font=("Consolas", 12), undo=True, wrap="word")
        self.txt_anotacoes.pack(side="left", fill="both", expand=True)

        v_scroll = ttk.Scrollbar(f_anotacoes, orient="vertical", command=self.txt_anotacoes.yview)
        v_scroll.pack(side="right", fill="y")
        self.txt_anotacoes.config(yscrollcommand=v_scroll.set)

        # Carregar anotações existentes
        conteudo = self.dados.get("anotacoes", "")
        self.txt_anotacoes.insert("1.0", conteudo)

        # Salvar ao digitar (debounce simples via after se fosse necessário, mas vamos salvar no on_closing ou em eventos)
        self.txt_anotacoes.bind("<KeyRelease>", self.salvar_anotacoes_evento)

    def salvar_anotacoes_evento(self, event=None):
        self.dados["anotacoes"] = self.txt_anotacoes.get("1.0", "end-1c")
        # Podemos salvar no arquivo periodicamente ou apenas quando fechar. 
        # Para segurança, vamos atualizar o objeto dados e deixar o salvar_dados global lidar com o arquivo.

    # ---------- Aba Histórico ----------
    def _preencher_historico_inicial(self):
        """
        Roda apenas uma vez, na primeira execução após a aba de Histórico
        ser criada. Não temos como saber as edições que já aconteceram
        antes deste recurso existir, então registramos o estado atual de
        cada jogador como ponto de partida ('Registro inicial'), para que
        nada do que já existe fique de fora do histórico.
        """
        agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        for nome_time, time in self.dados.get("times", {}).items():
            if isinstance(time, dict) and time.get("liga", False):
                continue
            for j in time.get("jogadores", []):
                detalhes = f"Posição {j.get('posicao','')}, Overall {j.get('overall','')}"
                nac = j.get("nacionalidade", "")
                if nac:
                    detalhes += f", Nacionalidade {nac}"
                self.historico.append({
                    "data": agora,
                    "tipo": "Registro inicial",
                    "jogador": j.get("nome", ""),
                    "time": nome_time,
                    "detalhes": detalhes + " (já existia antes da criação do histórico)"
                })
        salvar_historico(self.historico)

    def registrar_historico(self, tipo, jogador_nome, time_nome, detalhes=""):
        entrada = {
            "data": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
            "tipo": tipo,
            "jogador": jogador_nome,
            "time": time_nome,
            "detalhes": detalhes
        }
        self.historico.append(entrada)
        salvar_historico(self.historico)
        if hasattr(self, "tree_historico"):
            self.atualizar_historico()

    def montar_historico(self):
        f_historico = ttk.Frame(self.pagina_historico, padding=10)
        f_historico.pack(fill="both", expand=True)

        f_filtro = ttk.Frame(f_historico)
        f_filtro.pack(fill="x", pady=(0, 10))
        ttk.Label(f_filtro, text="Buscar jogador:", font=("Helvetica", 10)).pack(side="left", padx=(0, 8))
        self.e_filtro_historico = ttk.Entry(f_filtro, width=30)
        self.e_filtro_historico.pack(side="left")
        self.e_filtro_historico.bind("<KeyRelease>", lambda e: self.atualizar_historico())
        ttk.Button(f_filtro, text="Atualizar", command=self.atualizar_historico).pack(side="left", padx=10)

        cols = ("Data", "Tipo", "Jogador", "Time", "Detalhes")
        self.tree_historico = ttk.Treeview(f_historico, columns=cols, show="headings")
        larguras = {"Data": 130, "Tipo": 120, "Jogador": 160, "Time": 150, "Detalhes": 420}
        for c in cols:
            self.tree_historico.heading(c, text=c)
            self.tree_historico.column(c, width=larguras.get(c, 120), anchor="w")

        v_scroll = ttk.Scrollbar(f_historico, orient="vertical", command=self.tree_historico.yview)
        self.tree_historico.configure(yscrollcommand=v_scroll.set)
        self.tree_historico.pack(side="left", fill="both", expand=True)
        v_scroll.pack(side="right", fill="y")

        self.atualizar_historico()

    def atualizar_historico(self):
        filtro = remover_acentos(self.e_filtro_historico.get().strip()) if hasattr(self, "e_filtro_historico") else ""
        self.tree_historico.delete(*self.tree_historico.get_children())
        # Mais recentes primeiro
        for entrada in reversed(self.historico):
            if filtro and filtro not in remover_acentos(entrada.get("jogador", "")):
                continue
            self.tree_historico.insert("", "end", values=(
                entrada.get("data", ""),
                entrada.get("tipo", ""),
                entrada.get("jogador", ""),
                entrada.get("time", ""),
                entrada.get("detalhes", "")
            ))

    def atualizar_tudo(self):
        self.atualizar_times()
        self.atualizar_jogadores_time()
        self.atualizar_jogadores_geral()

    def proximo_foco(self, event, widget):
        widget.focus_set()
        return "break"

    def anterior_foco(self, event, widget):
        widget.focus_set()
        return "break"


if __name__ == "__main__":
    # Identidade própria do app no Windows: sem isso, o Windows pode agrupar
    # este programa junto com outros scripts Python na barra de tarefas/Menu
    # Iniciar e usar o ícone genérico do Python em vez do ícone do programa.
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("PES2021Manager.App")
        except Exception:
            pass

    root = tk.Tk()
    try:
        _icone_path = os.path.join(_BASE_DIR, "bola_vermelha.ico")
        if os.path.exists(_icone_path):
            root.iconbitmap(_icone_path)
    except Exception:
        pass  # se o ícone não existir/for inválido, segue sem travar o programa
    app = App(root)
    root.mainloop()
