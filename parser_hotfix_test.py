import financial_data_engine as fde


def run_case(name, html, expected):
    old = fde.disclosure_body_html
    try:
        fde.parse_financial_report.cache_clear()
        fde.disclosure_body_html = lambda _id: html
        out = fde.parse_financial_report(999999)
        cur = out['current']
        comp = out['comparison']
        for key, exp in expected['current'].items():
            got = cur.get(key)
            assert got == exp, (name, key, got, exp)
        for key, exp in expected.get('comparison', {}).items():
            got = comp.get(key)
            assert got == exp, (name, 'comparison.'+key, got, exp)
        print(name, 'OK')
    finally:
        fde.disclosure_body_html = old
        fde.parse_financial_report.cache_clear()


THYAO = '''
<table>
<tr><td>Sunum Para Birimi</td><td>Milyon TL</td></tr>
<tr><td>Hasılat</td><td>21</td><td>585.069</td><td>408.036</td></tr>
<tr><td>Esas Faaliyet Kârı (Zararı)</td><td>25</td><td>-5.098</td><td>24.529</td></tr>
<tr><td>Ana Ortaklık Payları</td><td>19</td><td>18.864</td><td>25.013</td></tr>
<tr><td>Toplam Özkaynaklar</td><td>1.018.453</td><td>911.256</td></tr>
</table>
'''

AKCNS = '''
<table>
<tr><td>Sunum Para Birimi</td><td>1.000 TL</td></tr>
<tr><td>Hasılat</td><td>13.670.000</td><td>13.030.000</td></tr>
<tr><td>Esas Faaliyet Kârı (Zararı)</td><td>-362.003</td><td>69.115</td></tr>
<tr><td>Dönem Kârı (Zararı)</td><td>-96.377</td><td>91.806</td></tr>
<tr><td>Toplam Özkaynaklar</td><td>28.530.000</td><td>27.000.000</td></tr>
</table>
'''

run_case('THYAO', THYAO, {
    'current': {
        'hasilat': 585_069_000_000.0,
        'faaliyet_kari': -5_098_000_000.0,
        'net_kar': 18_864_000_000.0,
        'ozkaynak': 1_018_453_000_000.0,
    },
    'comparison': {
        'hasilat': 408_036_000_000.0,
        'faaliyet_kari': 24_529_000_000.0,
        'net_kar': 25_013_000_000.0,
    }
})

run_case('AKCNS', AKCNS, {
    'current': {
        'hasilat': 13_670_000_000.0,
        'faaliyet_kari': -362_003_000.0,
        'net_kar': -96_377_000.0,
        'ozkaynak': 28_530_000_000.0,
    },
    'comparison': {
        'hasilat': 13_030_000_000.0,
        'faaliyet_kari': 69_115_000.0,
        'net_kar': 91_806_000.0,
    }
})

print('Parser hotfix 2/2 BASARILI')
