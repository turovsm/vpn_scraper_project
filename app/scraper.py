import os
import sys
import threading
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(os.path.dirname(__file__), "browsers")
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import requests
import time
from requests.exceptions import SSLError, ConnectionError
from bs4 import BeautifulSoup
from app.models import VPNServer, VPNFile, db
import pycountry
from playwright.async_api import async_playwright
import asyncio
import shutil
import random
from sqlalchemy import MetaData
from sqlalchemy.exc import SQLAlchemyError
from app import create_app


app = create_app()
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///../instance/vpn_scraper.db'


def clear_database():
    try:
        with app.app_context():
            meta = MetaData()
            meta.reflect(bind=db.engine)
            for table in reversed(meta.sorted_tables):
                db.session.execute(table.delete())
            db.session.commit()
        print("Database cleared successfully.")
    except SQLAlchemyError as e:
        db.session.rollback()
        print(f"Failed to clear database: {e}")


def cleanup(files_dir):
    clear_database()
    if os.path.exists(files_dir):
        shutil.rmtree(files_dir)
        print(f"Deleted ovpn files folder: {files_dir}")
    else:
        print(f"Ovpn file folder not found: {files_dir}")


def get_country_code(country_name):
    try:
        return pycountry.countries.search_fuzzy(country_name)[0].alpha_2.lower()
    except LookupError:
        return "unknown"


def download_ovpn_file(link, directory, filename, retries=5, backoff_factor=2):
    if not os.path.exists(directory):
        os.makedirs(directory)

    filepath = os.path.join(directory, filename)
    for attempt in range(retries):
        try:
            response = requests.get(link, stream=True, timeout=10, verify=True)
            response.raise_for_status()
            with open(filepath, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)
            with app.app_context():
                latest_file = db.session.query(VPNFile).order_by(VPNFile.id.desc()).first()
                new_file_id = (latest_file.id + 1) if latest_file else 1
                new_vpn_file = VPNFile(id=new_file_id, file_name=filename)
                db.session.add(new_vpn_file)
                db.session.commit()
            return new_file_id
        except (SSLError, ConnectionError, requests.Timeout) as e:
            print(f"Transient error: {e}. Retrying ({attempt + 1}/{retries})...")
            time.sleep(backoff_factor ** attempt + random.uniform(0, 1))
        except requests.exceptions.RequestException as e:
            print(f"Non-recoverable error: {e}. Skipping...")
            break
        except Exception as e:
            print(f"Unexpected error: {e}. Skipping this file.")
            break

    print(f"Failed to download {link} after {retries} attempts.")
    return None



def scrape_ipspeed_info():
    with app.app_context():
        url = "https://ipspeed.info/freevpn_openvpn.php?language=en"
        source_website = "https://ipspeed.info"

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
        except (SSLError, ConnectionError, requests.Timeout) as e:
            print(f"Failed to fetch the webpage: {e}")
            return

        soup = BeautifulSoup(response.text, "html.parser")
        div_elements = soup.find_all("div", class_="list")[4:]

        for i in range(0, len(div_elements), 4):
            location = div_elements[i].get_text(strip=True)
            country_code = get_country_code(location)
            ip_protocol_div = div_elements[i + 1]
            ip_protocol = ip_protocol_div.get_text(strip=True)
            anchor_tag = ip_protocol_div.find_all("a")
            uptime = div_elements[i + 2].get_text(strip=True)
            if uptime.find(' mins') != -1:
                continue
            if uptime.find('days') != -1:
                days = int(uptime[:uptime.find(' days')])
                uptime = days*24
            elif uptime.find(' hours'):
                uptime = int(uptime[:uptime.find(' hours')])
            ping = div_elements[i + 3].get_text(strip=True)
            if uptime == 0 or ping[0] == "-" or ping[0] == "":
                continue
            ping = ping[:ping.find(' ms')]
            ids = ""
            for ach in anchor_tag:
                if ach:
                    openvpn_link = f"https://ipspeed.info{ach['href']}"
                    file_path = os.path.join(os.path.join(os.path.dirname(__file__), "static"), "files")
                    file_id = download_ovpn_file(openvpn_link, file_path, ach['href'][6:])
                    if file_id:
                        if ids == "":
                            ids = str(file_id)
                        else:
                            ids += f",{file_id}"

            vpn_server = VPNServer(
                country=location,
                country_code=country_code,
                uptime=uptime,
                ping=ping,
                source_website=source_website,
                vpn_file_ids=ids
            )

            db.session.add(vpn_server)
            db.session.commit()
            print(f"Added VPN Server: {location}, {ip_protocol}")
        print("Scraping completed successfully!")


async def scrape_vpngate_jp():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        url = "https://www.vpngate.net/en/"
        await page.goto(url, timeout=40000)
        tables = await page.query_selector_all("#vg_hosts_table_id")
        table = tables[2]
        tbody = await table.query_selector("tbody")
        rows = await tbody.query_selector_all("tr")
        print(f"Number of rows: {len(rows)}")
        for row in rows:
            location_cell = await row.query_selector("td:nth-child(1)")
            location = (await location_cell.inner_text()).strip() if location_cell else "Unknown"
            if location.startswith("Country"):
                continue
            country_code = get_country_code(location)
            uptime_cell = await row.query_selector("td:nth-child(3)")
            uptime = (await uptime_cell.inner_text()).strip() if uptime_cell else "No Uptime"
            idx1 = uptime.find('sessions')
            idx2 = uptime.find('Total')
            uptime = uptime[idx1 + 9:idx2 - 1]
            net_stats_cell = (await (await row.query_selector("td:nth-child(4)")).inner_text()).strip()
            speed = net_stats_cell[:net_stats_cell.find("Mbps") - 4].replace(",", "")
            ping = net_stats_cell[net_stats_cell.find("Ping:") + 6:]
            ping = ping[:ping.find("\n")]
            ip_protocol_cell = (await (await row.query_selector("td:nth-child(7)")).inner_text()).strip()
            operator_cell = (await (await row.query_selector("td:nth-child(9)")).inner_text()).strip()
            protocols = 0

            if uptime.find(' mins') != -1:
                continue
            if uptime.find(' days') != -1:
                days = int(uptime[:uptime.find(' days')])
                uptime = days*24
            elif uptime.find(' hours'):
                uptime = int(uptime[:uptime.find(' hours')])

            if int(speed) < 50 or ping[0] == "-" or ping[0] == "" or not ip_protocol_cell.startswith("OpenVPN") or operator_cell.startswith("By Daiyuu Nobori"):
                continue
            if ip_protocol_cell.find("UDP") != -1 and ip_protocol_cell.find("TCP") != -1:
                tcp = ip_protocol_cell[25:ip_protocol_cell.find("UDP") - 1]
                udp = ip_protocol_cell[ip_protocol_cell.find("UDP") + 5:]
                protocols = 3
            elif ip_protocol_cell.find("UDP") == -1 and ip_protocol_cell.find("TCP") != -1:
                tcp = ip_protocol_cell[ip_protocol_cell.find("TCP") + 5:]
                protocols = 1
            elif ip_protocol_cell.find("UDP") != -1 and ip_protocol_cell.find("TCP") == -1:
                udp = ip_protocol_cell[ip_protocol_cell.find("UDP") + 5:]
                protocols = 2
            else:
                continue
            link_element = await (await row.query_selector("td:nth-child(7)")).query_selector("a")
            if not link_element:
                continue
            link = "https://download.vpngate.jp/en/" + await link_element.get_attribute('href')
            try:
                ids = await get_file_vpngate(link)
            except Exception as e:
                print(f"Failed to fetch file: {e}")
            ping = ping[:ping.find(' ms')]
            if location == "Korea Republic of":
                country_code = "kr"
            if ids is None:
                continue
            vpn_server = VPNServer(
                country=location,
                country_code=country_code,
                uptime=uptime,
                ping=ping,
                source_website=url,
                vpn_file_ids=ids
            )

            db.session.add(vpn_server)
            db.session.commit()
            print(f"Added VPN Server: {location}")
        await browser.close()
        print("Scraping completed successfully!")


async def get_file_vpngate(link):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(link, timeout=40000)
            ids = ""
            anchors = await page.query_selector_all("a")
            links = [await anchor.get_attribute("href") for anchor in anchors if await anchor.get_attribute("href")]
            for link in links:
                if len(link) > 45 and link.find("opengw") == -1 and link.find("vpngate_") != -1:
                    full_link = f"https://download.vpngate.jp{link}"
                    file_path = os.path.join(os.path.join(os.path.dirname(__file__), "static"), "files")
                    file_id = download_ovpn_file(full_link, file_path, link[link.find("vpngate_"):])
                    if ids == "":
                        ids = str(file_id)
                    else:
                        ids += f",{file_id}"
        except Exception as e:
            print(f"Error during page navigation: {e}")
        finally:
            await browser.close()
            return ids


async def download_with_playwright(page, download_url, target_directory, filename):
    os.makedirs(target_directory, exist_ok=True)
    file_path = os.path.join(target_directory, filename)
    async with page.expect_download() as download_info:
        await page.goto(download_url)
    download = await download_info.value
    await download.save_as(file_path)
    with app.app_context():
        latest_file = db.session.query(VPNFile).order_by(VPNFile.id.desc()).first()
        new_file_id = (latest_file.id + 1) if latest_file else 1
        new_vpn_file = VPNFile(id=new_file_id, file_name=filename)
        db.session.add(new_vpn_file)
        db.session.commit()

        return new_file_id


def looping():
    try:
        while True:
            cleanup(files_dir=os.path.join(os.path.join(os.path.dirname(__file__), "static"), "files"))
            print("Starting scraping...")
            with app.app_context():
                scrape_ipspeed_info()
                asyncio.run(scrape_vpngate_jp())
            print("Sleeping for 3 hours... zzzz")
            time.sleep(10800)
    except KeyboardInterrupt:
        print("Scraper interrupted. Exiting gracefully.")

def run_flask():
    app.run(debug=True, use_reloader=False)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    looping()
