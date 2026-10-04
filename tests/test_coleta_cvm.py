"""poc/coleta_cvm.py com um zip sintético no layout dos Dados Abertos da CVM (sem rede).

Os valores reproduzem o 1T25 e o 2T25 do release da Petrobras; a conferência com os arquivos
reais da CVM roda no workflow valida-coleta.yml (precisa de rede)."""
import importlib.util
import io
import pathlib
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("cvm", ROOT / "poc" / "coleta_cvm.py")
cvm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cvm)

CAB = "CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;GRUPO_DFP;MOEDA;ESCALA_MOEDA;ORDEM_EXERC;DT_INI_EXERC;DT_FIM_EXERC;CD_CONTA;DS_CONTA;VL_CONTA;ST_CONTA_FIXA"


def _l(ini, fim, conta, desc, v_mi, versao=1, ordem="ÚLTIMO"):
    return f"33.000.167/0001-01;{fim};{versao};PETROLEO BRASILEIRO S.A. PETROBRAS;009512;DF Consolidado;REAL;MIL;{ordem};{ini};{fim};{conta};{desc};{v_mi * 1000};S"


def _zip():
    dre = [_l("2025-01-01", "2025-03-31", "3.01", "Receita de Venda de Bens e/ou Serviços", 123144),
           _l("2025-01-01", "2025-03-31", "3.06", "Resultado Financeiro", 10595),
           _l("2025-01-01", "2025-03-31", "3.07", "Resultado Antes dos Tributos sobre o Lucro", 53635),
           _l("2025-01-01", "2025-03-31", "3.11.01", "Atribuído a Sócios da Empresa Controladora", 35209),
           _l("2025-04-01", "2025-06-30", "3.01", "Receita de Venda de Bens e/ou Serviços", 119128),
           _l("2025-01-01", "2025-06-30", "3.01", "Receita de Venda de Bens e/ou Serviços", 242272),
           _l("2025-04-01", "2025-06-30", "3.06", "Resultado Financeiro", 5572),
           _l("2025-04-01", "2025-06-30", "3.07", "Resultado Antes dos Tributos sobre o Lucro", 36040),
           _l("2025-04-01", "2025-06-30", "3.11.01", "Atribuído a Sócios da Empresa Controladora", 26652),
           _l("2025-01-01", "2025-03-31", "3.01", "Receita (exercício anterior)", 1, ordem="PENÚLTIMO")]
    dfc = [_l("2025-01-01", "2025-03-31", "6.01", "Caixa Líquido Atividades Operacionais", 49338),
           _l("2025-01-01", "2025-03-31", "6.01.01.02", "Depreciação, depleção e amortização", 18976),
           _l("2025-01-01", "2025-03-31", "6.02.01", "Aquisições de ativos imobilizados e intangíveis", -23297),
           _l("2025-01-01", "2025-06-30", "6.01", "Caixa Líquido Atividades Operacionais", 91762),
           _l("2025-01-01", "2025-06-30", "6.01.01.02", "Depreciação, depleção e amortização", 39928),
           _l("2025-01-01", "2025-06-30", "6.02.01", "Aquisições de ativos imobilizados e intangíveis", -46467)]
    bpa = [_l("", "2025-03-31", "1.01.01", "Caixa e Equivalentes de Caixa", 40000),
           _l("", "2025-03-31", "1.01.02", "Títulos e valores mobiliários", 8000)]
    bpp = [_l("", "2025-03-31", "2.01.04", "Financiamentos", 30000),
           _l("", "2025-03-31", "2.02.01", "Financiamentos", 160000),
           _l("", "2025-03-31", "2.01.05.02.01", "Arrendamentos", 40000),
           _l("", "2025-03-31", "2.02.02.02.01", "Arrendamentos", 139748),
           _l("", "2025-03-31", "2.02.01", "Financiamentos", 999999, versao=0)]
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for nome, ls in [("DRE", dre), ("DFC_MI", dfc), ("BPA", bpa), ("BPP", bpp)]:
            z.writestr(f"itr_cia_aberta_{nome}_con_2025.csv", ("\n".join([CAB] + ls)).encode("latin-1"))
    return b.getvalue()


def test_cvm_reproduz_o_release_no_1t25():
    v = cvm.trimestre(cvm.linhas(_zip()), "2025-Q1")
    assert v["receita_brl"] == 123144 and v["lucro_liquido_brl"] == 35209
    assert v["ebitda_brl"] == 62016  # 53.635 − 10.595 + 18.976 (RCVM 156)
    assert v["fco_brl"] == 49338 and v["capex_brl"] == 23297
    assert v["divida_liquida_brl"] == 30000 + 160000 + 40000 + 139748 - 40000 - 8000


def test_dfc_acumulada_vira_trimestre_isolado():
    v = cvm.trimestre(cvm.linhas(_zip()), "2025-Q2")
    assert v["receita_brl"] == 119128  # DRE traz o trimestre isolado
    assert v["fco_brl"] == 91762 - 49338 and v["capex_brl"] == 46467 - 23297
    assert v["ebitda_brl"] == 36040 - 5572 + (39928 - 18976)


def test_ignora_exercicio_anterior_e_versao_antiga():
    ls = cvm.linhas(_zip())
    assert not any(l["desc"].startswith("receita (exercicio") for l in ls)
    assert all(l["valor"] != 999999 for l in ls)


def test_titulos_de_longo_prazo_entram_nas_disponibilidades():
    """No ITR real do 1T25 a Petrobras tem R$ 4.806 mi em 1.02.01.03 (custo amortizado); o release os desconta."""
    extra = [_l("", "2025-03-31", "1.02.01", "Ativo Realizável a Longo Prazo", 60000),
             _l("", "2025-03-31", "1.02.01.01", "Aplicações Financeiras Avaliadas a Valor Justo através do Resultado", 0),
             _l("", "2025-03-31", "1.02.01.03", "Aplicações Financeiras Avaliadas ao Custo Amortizado", 4806)]
    base = cvm.linhas(_zip())
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("itr_cia_aberta_BPA_con_2025.csv", ("\n".join([CAB] + extra)).encode("latin-1"))
    v = cvm.trimestre(base + cvm.linhas(b.getvalue()), "2025-Q1")
    assert v["titulos_brl"] == 8000 + 4806
    assert v["divida_liquida_brl"] == 30000 + 160000 + 40000 + 139748 - 40000 - 8000 - 4806
