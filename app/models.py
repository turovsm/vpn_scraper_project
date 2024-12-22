from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class VPNServer(db.Model):
    __tablename__ = 'vpn_servers'
    id = db.Column(db.Integer, primary_key=True)
    country = db.Column(db.String(120), nullable=False)
    country_code = db.Column(db.String(10), nullable=False)
    uptime = db.Column(db.Integer, nullable=True)
    ping = db.Column(db.Integer, nullable=True)
    source_website = db.Column(db.String(255), nullable=False)
    vpn_file_ids = db.Column(db.String(255), nullable=True)

class VPNFile(db.Model):
    __tablename__ = 'vpn_files'
    id = db.Column(db.Integer, primary_key=True)
    file_name = db.Column(db.String(255), nullable=False)