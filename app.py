from flask import Flask, render_template, redirect, url_for, request, session, flash
from flask_sqlalchemy import SQLAlchemy
from google.colab.output import eval_js

app = Flask(__name__)
app.config['SECRET_KEY'] = 'kuncirahasiadispen123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ========================================================
# DATABASE MODEL
# ========================================================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(50), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    nama = db.Column(db.String(100), nullable=False)
    kelas = db.Column(db.String(20), nullable=True)

class Dispensasi(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    siswa_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    pembina_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    kelas_siswa = db.Column(db.String(20), default='X-2')
    tipe = db.Column(db.String(20), nullable=False) # 'internal' atau 'eksternal'
    alasan = db.Column(db.Text, nullable=False)
    tanggal = db.Column(db.String(20), nullable=False)
    waktu_mulai = db.Column(db.String(10), default='07:00')
    waktu_selesai = db.Column(db.String(10), default='12:00')
    status_piket = db.Column(db.String(20), default='Menunggu')
    status_waka = db.Column(db.String(20), default='Menunggu')

    @property
    def status_akhir(self):
        if self.tipe == 'internal':
            if self.status_piket == 'setuju': return 'Disetujui'
            elif self.status_piket == 'tolak': return 'Ditolak'
            return 'Sedang Diproses'
        else:
            if self.status_piket == 'tolak' or self.status_waka == 'tolak': return 'Ditolak'
            elif self.status_piket == 'setuju' and self.status_waka == 'setuju': return 'Disetujui'
            return 'Sedang Diproses'

    siswa = db.relationship('User', foreign_keys=[siswa_id])
    pembina = db.relationship('User', foreign_keys=[pembina_id])

# ========================================================
# ROUTING & LOGIC
# ========================================================
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session['user_id'] = user.id
            session['role'] = user.role
            session['nama'] = user.nama
            session['kelas'] = user.kelas

            if user.role == 'siswa': return redirect(url_for('dashboard_siswa'))
            elif user.role == 'pembina': return redirect(url_for('dashboard_pembina'))
            elif user.role == 'piket': return redirect(url_for('dashboard_piket'))
            elif user.role == 'waka': return redirect(url_for('dashboard_waka'))
            elif user.role == 'guru_kelas': return redirect(url_for('dashboard_guru'))
    return render_template('login.html')

@app.route('/dashboard/siswa')
def dashboard_siswa():
    if 'user_id' not in session or session['role'] != 'siswa': return redirect(url_for('login'))
    riwayat_saya = Dispensasi.query.filter_by(siswa_id=session['user_id']).all()
    return render_template('dashboard_siswa.html', riwayat=riwayat_saya, nama=session['nama'])

@app.route('/dashboard/pembina')
def dashboard_pembina():
    if 'user_id' not in session or session['role'] != 'pembina': return redirect(url_for('login'))
    my_riwayat = Dispensasi.query.filter_by(pembina_id=session['user_id']).all()
    return render_template('dashboard_pembina.html', riwayat=my_riwayat, nama=session['nama'])

@app.route('/dashboard/pembina/ajukan', methods=['GET', 'POST'])
def dashboard_pembina_ajukan():
    if 'user_id' not in session or session['role'] != 'pembina': return redirect(url_for('login'))

    if request.method == 'POST':
        tipe_input = request.form.get('tipe')
        # Normalkan string status menjadi lowercase agar konsisten
        waka_init = 'Tidak Diperlukan' if tipe_input == 'internal' else 'Menunggu'

        baru = Dispensasi(
            siswa_id=request.form.get('siswa_id'),
            pembina_id=session['user_id'],
            kelas_siswa=request.form.get('kelas_siswa'),
            tipe=tipe_input,
            alasan=request.form.get('alasan'),
            tanggal=request.form.get('tanggal'),
            waktu_mulai=request.form.get('waktu_mulai', '07:00'),
            waktu_selesai=request.form.get('waktu_selesai', '12:00'),
            status_piket='Menunggu',
            status_waka=waka_init
        )
        db.session.add(baru)
        db.session.commit()
        return redirect(url_for('dashboard_pembina'))

    siswa_list = User.query.filter_by(role='siswa').all()
    return render_template('form_pembina.html', siswa_list=siswa_list, nama=session['nama'])

@app.route('/dashboard/piket')
def dashboard_piket():
    if 'user_id' not in session or session['role'] != 'piket': return redirect(url_for('login'))
    return render_template('dashboard_piket.html', riwayat=Dispensasi.query.all(), nama=session['nama'])

@app.route('/dashboard/waka')
def dashboard_waka():
    if 'user_id' not in session or session['role'] != 'waka': return redirect(url_for('login'))
    return render_template('dashboard_waka.html', riwayat=Dispensasi.query.all(), nama=session['nama'])

@app.route('/dashboard/guru')
def dashboard_guru():
    if 'user_id' not in session or session['role'] != 'guru_kelas': return redirect(url_for('login'))
    return render_template('dashboard_guru.html', riwayat=Dispensasi.query.all(), nama=session['nama'])

# ========================================================
# PERBAIKAN ROUTE AKSI (GURU PIKET & WAKA)
# ========================================================

@app.route('/aksi/piket/<int:id>/<string:status>')
def aksi_piket_baru(id, status):
    if 'user_id' not in session or session['role'] != 'piket': return redirect(url_for('login'))
    dispen = Dispensasi.query.get_or_404(id)
    dispen.status_piket = status # menerima 'setuju' atau 'tolak'
    db.session.commit()
    return redirect(url_for('dashboard_piket'))

@app.route('/aksi/waka/<int:id>/<string:status>')
def aksi_waka_baru(id, status):
    if 'user_id' not in session or session['role'] != 'waka': return redirect(url_for('login'))
    dispen = Dispensasi.query.get_or_404(id)
    dispen.status_waka = status # menerima 'setuju' atau 'tolak'
    db.session.commit()
    return redirect(url_for('dashboard_waka'))

# ========================================================
# LOGOUT
# ========================================================
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        db.drop_all()
        db.create_all()
        db.session.add_all([
            User(username='250037', password='250037*', role='siswa', nama='AGHNIA KHAIRA AQILAH PUTRI', kelas='X - 2'),
            User(username='250038', password='250038*', role='siswa', nama='AISHA NAZIFA FAYI HASAN', kelas='X - 2'),
            User(username='250039', password='250039*', role='siswa', nama='AISYAH AMRU ASYSYIFA YUDIANTO', kelas='X - 2'),
            User(username='250040', password='250040*', role='siswa', nama='ALFIANO REALLY PUTRO ARYANTO', kelas='X - 2'),
            User(username='250041', password='250041*', role='siswa', nama='ALFIN HUSNUN ELISYIA', kelas='X - 2'),
            User(username='250042', password='250042*', role='siswa', nama='ALISA NAYLA IZZA', kelas='X - 2'),
            User(username='250043', password='250043*', role='siswa', nama='ALLEYNA MAHARANI PUTRI', kelas='X - 2'),
            User(username='250044', password='250044*', role='siswa', nama='ANGGUN RIZKA YURISTIA', kelas='X - 2'),
            User(username='250045', password='250045*', role='siswa', nama='AURUM NAIRA RAHMA', kelas='X - 2'),
            User(username='250046', password='250046*', role='siswa', nama='AZURA WALIYUL AKBAR', kelas='X - 2'),
            User(username='250047', password='250047*', role='siswa', nama='DAYANA KENZIE BATRISYA SUKARNO', kelas='X - 2'),
            User(username='250048', password='250048*', role='siswa', nama='DWI AYUFITRIYANI', kelas='X - 2'),
            User(username='250049', password='250049*', role='siswa', nama='FADLIKA INNOVA KAMIL', kelas='X - 2'),
            User(username='250051', password='250051*', role='siswa', nama='FAIZ FAQIH ZAKY MUCHAMMAD BINTANG AL KHALIFI', kelas='X - 2'),
            User(username='250052', password='250052*', role='siswa', nama='HAFIZH AMIRRUL ZAKI', kelas='X - 2'),
            User(username='250053', password='250053*', role='siswa', nama='JIHAN NUR AZIZAH', kelas='X - 2'),
            User(username='250054', password='250054*', role='siswa', nama='KARENINA HERSIWI LARASATI', kelas='X - 2'),
            User(username='250055', password='250055*', role='siswa', nama='LAKSITA KHANSA ZAFIRA', kelas='X - 2'),
            User(username='250056', password='250056*', role='siswa', nama='LAULA ALMIRA MA''WA', kelas='X - 2'),
            User(username='250057', password='250057*', role='siswa', nama='M.FAHMI SHOLIKHUL AMRY', kelas='X - 2'),
            User(username='250058', password='250058*', role='siswa', nama='MASSAYU PUTRI ALFA DININGTYAS', kelas='X - 2'),
            User(username='250059', password='250059*', role='siswa', nama='MOHAMMAD ABYAZ HAQQI', kelas='X - 2'),
            User(username='250060', password='250060*', role='siswa', nama='MUHAMAD ARDHAN DIAZ SABROE', kelas='X - 2'),
            User(username='250061', password='250061*', role='siswa', nama='MUHAMMAD YUSUF NUR FAIRUZ ABDUL MAJID', kelas='X - 2'),
            User(username='250062', password='250062*', role='siswa', nama='MUKHAMAD MIRZA ANANTA KHAIZURAN', kelas='X - 2'),
            User(username='250063', password='250063*', role='siswa', nama='NAFISA ELIYA KAMELA SETIAWAN', kelas='X - 2'),
            User(username='250064', password='250064*', role='siswa', nama='NAJWA HANIN SUGIHARTO', kelas='X - 2'),
            User(username='250065', password='250065*', role='siswa', nama='NAJWA WAHYU PANGESTI', kelas='X - 2'),
            User(username='250066', password='250066*', role='siswa', nama='NAURA ZAHIDA GUSNI PUTRI', kelas='X - 2'),
            User(username='250067', password='250067*', role='siswa', nama='QUEEN FELOVE MARTHA', kelas='X - 2'),
            User(username='250068', password='250068*', role='siswa', nama='RADITYA JAVAS NARARYA', kelas='X - 2'),
            User(username='250069', password='250069*', role='siswa', nama='RAIHANAH ROHADATUL AISY', kelas='X - 2'),
            User(username='250070', password='250070*', role='siswa', nama='RAZKA LAZUARDIO ALVARO', kelas='X - 2'),
            User(username='250071', password='250071*', role='siswa', nama='RIZKY IZZATY RAMADHANI', kelas='X - 2'),
            User(username='250072', password='250072*', role='siswa', nama='VERZOCARLO AZZAEL ALFATHIRSSA', kelas='X - 2'),
            User(username='2500504', password='2500504*', role='siswa', nama='M. AZKA ZAIDAN AQILA ROFIQ', kelas='X - 2'),
            User(username='BANTA CRISBIANTORO', password='BANTA CRISBIANTORO*', role='pembina', nama='BANTA CRISBIANTORO'),
            User(username='SAHWIYADI', password='SAHWIYADI*', role='pembina', nama='SAHWIYADI'),
            User(username='GIJOTO', password='GIJOTO*', role='pembina', nama='GIJOTO'),
            User(username='MARZUQI', password='MARZUQI*', role='pembina', nama='MARZUQI'),
            User(username='AHYA MUJAHIDIN', password='AHYA MUJAHIDIN*', role='pembina', nama='AHYA MUJAHIDIN'),
            User(username='DUWI HARTANTI', password='DUWI HARTANTI*', role='piket', nama='DUWI HARTANTI'),
            User(username='IIN HIKMAWATI', password='IIN HIKMAWATI*', role='waka', nama='IIN HIKMAWATI'),
            User(username='AGUS SETIADI', password='AGUS SETIADI*', role='waka', nama='AGUS SETIADI'),
            User(username='ARUJI YAHYA', password='ARUJI YAHYA*', role='waka', nama='ARUJI YAHYA'),
            User(username='TRIWIDIASTUTI SOEJONO', password='TRIWIDIASTUTI SOEJONO*', role='guru_kelas', nama='TRIWIDIASTUTI SOEJONO')
        ])
        db.session.commit()

    print("\n" + "="*50)
    print("KLIK LINK DI BAWAH INI UNTUK MEMBUKA WEBSITE KAMU:")
    print(eval_js("google.colab.kernel.proxyPort(5000)") + "/login")
    print("="*50 + "\n")

    app.run(port=5000)