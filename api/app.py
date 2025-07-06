import io
import requests
import pandas as pd
from flask import Flask, request, jsonify, send_file, render_template
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, urljoin

app = Flask(__name__)
LAST_RESULTS = []

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        " AppleWebKit/537.36 (KHTML, like Gecko)"
        " Chrome/117.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9"
}
TIMEOUT = 10

# HTTP GET helper
def fetch(url):
    try:
        return requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    except:
        return None

# --- Parser Functions ---

def parse_amazon(url):
    r = fetch(url)
    if not r or r.status_code != 200:
        return None
    soup = BeautifulSoup(r.text, 'html.parser')
    data = {'Site':'Amazon','link':url}
    t = soup.select_one('#productTitle')
    data['Model'] = t.get_text(strip=True) if t else ''
    p = soup.select_one('#priceblock_ourprice, #priceblock_dealprice') or soup.select_one('.a-price .a-offscreen')
    data['Price'] = p.get_text(strip=True) if p else ''
    # Specs table
    for row in soup.select('#productDetails_techSpec_section_1 tr'):
        k = row.select_one('th').get_text(strip=True)
        v = row.select_one('td').get_text(strip=True)
        data[k] = v
    # Bullets
    for li in soup.select('#feature-bullets ul li'):
        txt = li.get_text(strip=True)
        if ':' in txt:
            k,v = map(str.strip, txt.split(':',1))
            data.setdefault(k,v)
    return data


def parse_flipkart(url):
    r = fetch(url)
    if not r or r.status_code != 200:
        return None
    soup = BeautifulSoup(r.text, 'html.parser')
    data = {'Site':'Flipkart','link':url}
    t = soup.select_one('span.B_NuCI')
    data['Model'] = t.get_text(strip=True) if t else ''
    p = soup.select_one('div._30jeq3._16Jk6d')
    data['Price'] = p.get_text(strip=True) if p else ''
    for row in soup.select('table._14cfVK tr'):
        c = row.select('td')
        if len(c)==2:
            data[c[0].get_text(strip=True)] = c[1].get_text(strip=True)
    return data


def parse_croma(url):
    r = fetch(url)
    if not r or r.status_code!=200:
        return None
    soup = BeautifulSoup(r.text,'html.parser')
    data={'Site':'Croma','link':url}
    t = soup.select_one('h1.product-name') or soup.select_one('.prod-title h1')
    data['Model'] = t.get_text(strip=True) if t else ''
    p = soup.select_one('.price-section .final-price') or soup.select_one('.pd-price')
    data['Price'] = p.get_text(strip=True) if p else ''
    for li in soup.select('.spec-wrap li'):  # list specs
        if ':' in li.get_text():
            k,v = map(str.strip, li.get_text(strip=True).split(':',1))
            data[k]=v
    return data


def parse_reliance(url):
    r = fetch(url)
    if not r or r.status_code!=200:
        return None
    soup = BeautifulSoup(r.text,'html.parser')
    data={'Site':'Reliance','link':url}
    t = soup.select_one('h1.pdp-title')
    data['Model'] = t.get_text(strip=True) if t else ''
    p = soup.select_one('.pdp-price .pdp-final-price')
    data['Price'] = p.get_text(strip=True) if p else ''
    for row in soup.select('.pdp-specs__table tr'):
        cols=row.select('td')
        if len(cols)==2:
            data[cols[0].get_text(strip=True)]=cols[1].get_text(strip=True)
    return data

# --- Search Route ---

@app.route('/')
def home(): return render_template('index.html')

@app.route('/search')
def search():
    global LAST_RESULTS
    q=request.args.get('q','').strip()
    if not q: return jsonify([])
    results=[]
    # Amazon India
    r1=fetch(f"https://www.amazon.in/s?k={quote_plus(q)}")
    if r1:
        s1=BeautifulSoup(r1.text,'html.parser')
        links=[a['href'] for a in s1.select('a.a-link-normal.s-no-outline') if 'dp' in a.get('href','')]
        for href in links[:15]:
            rec=parse_amazon(urljoin('https://www.amazon.in',href.split('?')[0]))
            if rec: results.append(rec)
    # Flipkart
    r2=fetch(f"https://www.flipkart.com/search?q={quote_plus(q)}")
    if r2:
        s2=BeautifulSoup(r2.text,'html.parser')
        links=[a['href'] for a in s2.select('a._1fQZEK, a._2rpwqI') if '/p/' in a.get('href','')]
        for href in links[:15]:
            rec=parse_flipkart(urljoin('https://www.flipkart.com',href.split('?')[0]))
            if rec: results.append(rec)
    # Croma
    r3=fetch(f"https://www.croma.com/search/?text={quote_plus(q)}")
    if r3:
        s3=BeautifulSoup(r3.text,'html.parser')
        for a in s3.select('.product-listing__item a')[:10]:
            rec=parse_croma(urljoin('https://www.croma.com',a['href']))
            if rec: results.append(rec)
    # Reliance Digital
    r4=fetch(f"https://www.reliancedigital.in/search?q={quote_plus(q)}")
    if r4:
        s4=BeautifulSoup(r4.text,'html.parser')
        for a in s4.select('.prd-link')[:10]:
            rec=parse_reliance(urljoin('https://www.reliancedigital.in',a['href']))
            if rec: results.append(rec)
    LAST_RESULTS=results
    return jsonify(results)

@app.route('/export')
def export():
    if not LAST_RESULTS: return 'No data',400
    df=pd.DataFrame(LAST_RESULTS)
    buf=io.BytesIO()
    df.to_excel(buf,index=False,engine='openpyxl')
    buf.seek(0)
    return send_file(buf,download_name='comparison.xlsx',as_attachment=True,mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

if __name__=='__main__': app.run(host='0.0.0.0',port=5000)