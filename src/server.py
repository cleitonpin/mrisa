import argparse
import json
import pycurl
from flask import Flask, url_for, jsonify, request
from flask_cors import CORS, cross_origin
python3 = False
try:
    from StringIO import StringIO
except ImportError:
    python3 = True
    import io as bytesIOModule
from bs4 import BeautifulSoup
if python3:
    import certifi
from googlecloudapi import getCloudAPIDetails, saveImage
import os

SEARCH_URL = 'https://www.google.com/searchbyimage?hl=en-US&image_url='

app = Flask(__name__)


@app.route('/search', methods = ['POST'])
def search():
    if request.headers['Content-Type'] != 'application/json':
        return "Requests must be in JSON format. Please make sure the header is 'application/json' and the JSON is valid."
    client_json = json.dumps(request.json)
    client_data = json.loads(client_json)

    if 'cloud_api' in client_data and client_data['cloud_api'] == True:
        saveImage(client_data['image_url'])
        data = getCloudAPIDetails("./default.jpg")
        return jsonify(data)

    else:
        code = doImageSearch(SEARCH_URL + client_data['image_url'])

        if 'resized_images' in client_data and client_data['resized_images'] == True:
            return parseResults(code, resized=True)
        else:
            return parseResults(code)

def doImageSearch(full_url):
    # Directly passing full_url
    """Return the HTML page response."""

    if python3:
        returned_code = bytesIOModule.BytesIO()
    else:
        returned_code = StringIO()
    # full_url = SEARCH_URL + image_url

    if app.debug:
        print('POST: ' + full_url)

    conn = pycurl.Curl()
    if python3:
        conn.setopt(conn.CAINFO, certifi.where())
    conn.setopt(conn.URL, str(full_url))
    conn.setopt(conn.FOLLOWLOCATION, 1)
    conn.setopt(conn.USERAGENT, 'Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:61.0) Gecko/20100101 Firefox/61.0')
    conn.setopt(conn.WRITEFUNCTION, returned_code.write)
    conn.perform()
    conn.close()
    if python3:
        return returned_code.getvalue().decode('UTF-8')
    else:
        return returned_code.getvalue()

def parseResults(code, resized=False):
    """Parse/Scrape the HTML code for the info we want."""

    soup = BeautifulSoup(code, 'html.parser')

    results = {
        'links': [],
        'descriptions': [],
        'titles': [],
        'similar_images': [],
        'best_guess': ''
    }

    for div in soup.findAll('div', attrs={'class':'rc'}):
        sLink = div.find('a')
        results['links'].append(sLink['href'])

    for desc in soup.findAll('span', attrs={'class':'st'}):
        results['descriptions'].append(desc.get_text())

    for title in soup.findAll('h3', attrs={'class':'r'}):
        results['titles'].append(title.get_text())

    for similar_image in soup.findAll('div', attrs={'rg_meta'}):
        tmp = json.loads(similar_image.get_text())
        img_url = tmp['ou']
        results['similar_images'].append(img_url)

    for best_guess in soup.findAll('a', attrs={'class':'fKDtNb'}):
      results['best_guess'] = best_guess.get_text()

    if resized:
        results['resized_images'] = getDifferentSizes(soup)

    print("Successful search")

    return json.dumps(results)

def getDifferentSizes(soup):
    """
    Takes html code ( souped ) as input

    Returns google's meta info on the different sizes of the same image from different websites

    Returns a list of JSON objects of form

    {
        'rh': 'resource_host',
        'ru': 'resource_url',
        'rid': 'SOME_ID_USED_BY_GOOGLE',
        'ou': 'original_url of image
        'oh': 'orginal_height',
        'ow': 'original_width',
        'ity': 'image type',
        'tu': 'thumbnail_url of image', # Generated by google
        'th': 'thumbnail_height',
        'tw': 'thumbnail_width',
        's': 'summary'
        'itg': 'SOME UNKNOWN TERM',
        'pt': 'pt', # some short description (UNKNOWN TERM)
        'sc': "SOME UNKNOWN TERM",
        'id': 'SOME_ID_USED_BY_GOOGLE',
        'st': 'Site', # UNKOWN TERM
        'rt': 'UNKNOWN TERM',
        'isu': 'resource_host', # (UNKNOWN TERM)
    }

    """

    region = soup.find('div',{"class":"O1id0e"})

    span = region.find('span',{"class":"gl"})

    allsizes = False

    try:

        if span.a.get_text() == "All sizes":
            allsizes = True
        else:
            print("not all sizes")
            print(span)
    except Exception as e:
        print(str(e))
        return [{'error':'500','details':'no_images_found'}]

    if allsizes:
        new_url = "https://google.com" + span.a['href']

    resized_images_page = doImageSearch(new_url)

    new_soup = BeautifulSoup(resized_images_page,"lxml")

    main_div = new_soup.find('div',{"id":"search"})

    rg_meta_divs = main_div.findAll('div',{"class":"rg_meta notranslate"})

    results = []

    for item in rg_meta_divs:
        results.append(json.loads(item.text))

    return results

def main():
    parser = argparse.ArgumentParser(description='Meta Reverse Image Search API')
    parser.add_argument('-p', '--port', type=int, default=5000, help='port number')
    parser.add_argument('-d','--debug', action='store_true', help='enable debug mode')
    parser.add_argument('-c','--cors', action='store_true', default=False, help="enable cross-origin requests")
    parser.add_argument('-a', '--host', type=str, default='0.0.0.0', help="sets the address to serve on")
    args = parser.parse_args()

    if args.debug:
        app.debug = True

    if args.cors:
        CORS(app, resources=r'/search/*')
        app.config['CORS_HEADERS'] = 'Content-Type'

        global search
        search = cross_origin(search)
        print(" * Running with CORS enabled")

    port = int(os.environ.get("PORT", 5000))
    
    app.run(host='0.0.0.0', port=port)
  
if __name__ == '__main__':
    main()
