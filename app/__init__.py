from flask import Flask, render_template, request
from flask_migrate import Migrate
from app.models import db, VPNServer, VPNFile
import pycountry

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///../instance/vpn_scraper.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    migrate = Migrate(app, db)

    @app.route('/')
    def index():
        sort_by = request.args.get('sort_by', 'country_name')
        sort_order = request.args.get('sort_order', 'asc')

        if sort_by == 'country_name':
            vpns = VPNServer.query.order_by(
                VPNServer.country.asc() if sort_order == 'asc' else VPNServer.country.desc()).all()
        elif sort_by == 'uptime':
            vpns = VPNServer.query.order_by(
                VPNServer.uptime.asc() if sort_order == 'asc' else VPNServer.uptime.desc()).all()
        elif sort_by == 'ping':
            vpns = VPNServer.query.order_by(
                VPNServer.ping.asc() if sort_order == 'asc' else VPNServer.ping.desc()).all()
        else:
            vpns = VPNServer.query.all()

        vpn_data = []

        for vpn in vpns:
            vpn_ids = vpn.vpn_file_ids.split(',') if ',' in vpn.vpn_file_ids else [vpn.vpn_file_ids]

            file_names = []
            file_paths = []
            for vpn_id in vpn_ids:
                vpn_file = VPNFile.query.filter_by(id=int(vpn_id)).first()
                if vpn_file:
                    file_names.append(vpn_file.file_name)
                    file_paths.append(f"static/files/{vpn_file.file_name}")
                else:
                    file_names.append('Not Found')
                    file_paths.append('')

            files = list(zip(file_names, file_paths))

            country_name = None
            country_flag_path = None
            try:
                country = pycountry.countries.get(alpha_2=vpn.country_code)
                if country:
                    country_name = country.name
                    country_flag_path = f"static/flags/{vpn.country_code.lower()}.svg"
            except KeyError:
                country_name = vpn.country_code

            vpn_data.append({
                'country_name': country_name,
                'country_flag_path': country_flag_path,
                'uptime': vpn.uptime,
                'ping': vpn.ping,
                'files': files,
                'source': vpn.source_website
            })

        return render_template('index.html', vpns=vpn_data, sort_by=sort_by, sort_order=sort_order)

    return app
