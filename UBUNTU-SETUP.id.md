# Ubuntu 24.04+ — Port Linux

**Languages:** [English](UBUNTU-SETUP.md) · **Bahasa Indonesia**

Dukungan Linux native untuk **ePlus AI Toolkit**. Halaman ini mencakup Ubuntu 24.04+
dengan Python 3 dan Android SDK Platform-Tools. Toolkit ini memakai ulang engine
Python/Frida yang sudah ada (`ultra0.py`) dan dasbor Textual bersama melalui adapter
native yang sama seperti yang dipakai macOS (`macos_runner.py`). **PowerShell tidak
diperlukan dan tidak digunakan di Linux.**

> [!CAUTION]
> **Proyek tidak resmi. Berpotensi menimbulkan tagihan.** Langkah **2–5** dapat membuka
> checkout Google Play sungguhan dan mungkin menekan **Subscribe** secara otomatis. Sebuah
> penawaran yang muncul di daftar, harga fase pertama yang ditampilkan nol, atau pesan
> log "Subscribe attempted" **tidak** membuktikan kelayakan, langganan aktif, langganan
> gratis, atau perubahan tanggal perpanjangan. Verifikasi akun yang tepat, tagihan hari
> ini, harga di masa depan, dan tanggal perpanjangan langsung di Google Play sebelum
> checkout apa pun.

> [!WARNING]
> **Setup serta Langkah 0/1 tidak bebas efek samping.** Satu kali jalan dapat memasang
> Frida di sisi Android, mendorong modul billing bawaan
> (`assets/modules/module_521.b64`) ke perangkat, **menghapus proxy HTTP Android**
> (`settings put global http_proxy :0`), dan **menghentikan paksa aplikasi VPN** yang
> mencegat lalu lintas Play. Perubahan itu tetap ada setelah tool ditutup. Gunakan hanya
> perangkat resmi yang memang dikhususkan untuk ini.

## Kebutuhan

| Komponen | Kebutuhan |
| --- | --- |
| OS | Ubuntu 24.04+ (diuji pada 24.04.5), x86_64 atau arm64 |
| Python | 3.10+ (Ubuntu 24.04 membawa 3.12.3) |
| ADB | Android SDK Platform-Tools di `PATH`, atau `ADB_PATH=/path/to/adb` |
| Android | Perangkat/emulator **ter-root** dengan **Google Play Store** + **Google One**, sudah masuk ke akun yang Anda berwenang periksa |
| Frida | Host **16.5.9**, dipasang ke `.venv` proyek oleh launcher; `frida-server` di sisi Android harus versi yang cocok |
| Disk | ~500 MB untuk `.venv` dan Platform-Tools |

**VPS tanpa layar (headless) bukan runtime yang didukung** — lihat
[Kelayakan VPS](#kelayakan-vps).

## Instalasi

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip adb android-sdk-platform-tools-common unzip

git clone <url-fork-anda> google-ai
cd google-ai
sh run-linux.sh --help      # tidak butuh dependensi maupun akses perangkat
sh run-linux.sh --doctor    # inspeksi host + ADB, hanya baca
```

`--help` dan `--doctor` **tidak** memerlukan perangkat Android terhubung, dan `--doctor`
tidak menulis apa pun ke Android. Launcher membuat `.venv` lokal proyek pada eksekusi
pertama yang membutuhkannya; jika `python3-venv` tidak tersedia, launcher beralih ke
[`uv`](https://docs.astral.sh/uv/), dan jika keduanya gagal berhenti dengan kode keluar 2
beserta perintah `apt` yang tepat.

### Perintah

```bash
sh run-linux.sh --help       # cara pakai; tidak butuh dependensi maupun perangkat
sh run-linux.sh --doctor     # inspeksi host dan ADB; TIDAK menulis ke Android
sh run-linux.sh --check      # Diagnostik Langkah 0;        DAPAT mengubah Android
sh run-linux.sh --list       # Metadata penawaran Langkah 1; DAPAT mengubah Android
sh run-linux.sh               # TUI interaktif pada Langkah 1
sh run-linux.sh --step 2     # TUI dengan Langkah 2 terpilih; tidak pernah jalan otomatis
sh run-linux.sh --sequence   # TUI dengan kontrol urutan terpandu
```

Memilih langkah di TUI **tidak pernah** menjalankannya. Langkah 2–5 juga memunculkan
modal persetujuan, dan adapter menambahkan `--confirmed` (Langkah 2–5) serta
`--active-confirmed` (Langkah 3–5) sebagai gerbang kedua yang gagal-tertutup. Kode keluar:

| Kode | Arti |
| --- | --- |
| 0 | Berhasil / cara pakai ditampilkan |
| 2 | Prasyarat kurang (Python < 3.10, tidak ada tooling venv, platform salah) |
| 3 | ADB tidak ada, tidak ada perangkat online, atau perangkat `unauthorized`/`offline` |
| 4 | Ada beberapa perangkat berbeda yang online; pemilihan ambigu |

## Keluaran yang diharapkan

`sh run-linux.sh --doctor` pada host tanpa perangkat terpasang:

```
ePlus AI Toolkit - Linux doctor (read-only)
  Host OS      Linux 6.x (x86_64)
  Python       3.12.3 at /usr/bin/python3
  Git          git version 2.43.0
  Project venv present
  Host Frida   16.5.9 (pinned 16.5.9)
  ADB          /usr/bin/adb
    Android Debug Bridge version 1.0.41
  Devices      1 reported, 1 online
    emulator-5554  [device]
  Device facts (read-only):
    ABI               arm64-v8a
    Android release   14 (SDK 34)
    Root (adb shell)  yes
    Google Play Store installed
    Google One        installed
    frida-server      running
    Frida device match uses USB transports only; ADB port forwarding alone
    does not establish a usable Frida target.

  No Android settings, packages, or processes were changed by this command.
  Next: sh run-linux.sh --check  (Step 0; MAY modify the Android device)
```

Tanpa perangkat: `Devices 0 reported, 0 online` dan kode keluar 3. Dengan dua perangkat
online: kode keluar 4 dan tool menolak menebak.

## Izin perangkat USB

Periksa dulu sebelum mengubah apa pun:

```bash
ls /etc/udev/rules.d/                 # aturan yang sudah ada
groups                                # apakah user Anda ada di plugdev?
adb devices -l
```

Paket `android-sdk-platform-tools-common` dari Ubuntu biasanya sudah memasang aturan
`udev` yang memadai. Tambahkan aturan yang **cakupannya sempit** hanya untuk vendor ID
yang benar-benar belum punya, lalu
`sudo udevadm control --reload-rules && sudo udevadm trigger`. Jangan pernah mengaktifkan
debugging tanpa batas, dan jangan pernah mematikan firewall secara global. Untuk emulator,
`adb connect 127.0.0.1:<port>` lewat loopback lebih disarankan daripada membuka transport
TCP ke luar.

## Konfigurasi Android yang diubah proyek ini

Jalankan `sh run-linux.sh --check` hanya pada **perangkat resmi yang dikhususkan**.
Yang akan terjadi:

- **Pemasangan Frida**: mengunduh build resmi `frida-server` 16.5.9 yang cocok dengan ABI
  perangkat dan menjalankannya sebagai root (`/data/local/tmp/frida-server`).
- **Modul billing**: mendorong payload APK/DEX berenkode base64 dari repo
  (`assets/modules/module_521.b64`) ke perangkat. **Komponen ini belum diaudit secara
  independen** — tinjau dulu sebelum dipakai.
- **Reset proxy HTTP**: `settings put global http_proxy :0` bila ada proxy terpasang.
- **Penanganan VPN**: menghentikan paksa paket Clash yang dikenal mencegat lalu lintas
  Play. Anda harus menyalakannya kembali sendiri setelahnya.
- **ADB root**: dapat menjalankan `adb root` atau `su -c` untuk memperoleh shell root.

Engine tidak pernah menambah atau mengganti akun Google pada rute terjaga yang dipakai di
sini (`--no-add --no-switch`) dan tidak pernah meneruskan `--force`.

## Keamanan penagihan

Langkah 2–5 dapat membuat tagihan Google Play sungguhan. Pada urutan 24 bulan yang
dilaporkan saat ini, Langkah 2, 3, dan 4 masing-masing melibatkan **peristiwa verifikasi
kartu ~US$1 yang terpisah**: **3 × US$1 = US$3** dalam tiga transaksi, bukan satu tagihan
US$3. Peristiwa tersebut bisa berupa otorisasi sementara (hold), bukan tagihan yang
final, dan biasanya hilang dalam 1–14 hari kerja tergantung bank. Fase pengenalan
berharga nol **bukan** bukti kelayakan maupun bukti perpanjangan gratis. Langkah 5
opsional dan di luar contoh tersebut.

Toolkit tidak pernah memakai `--force` untuk melewati verifikasi akun Play dan tidak dapat
mengubah kelayakan. Tinjau setiap checkout sungguhan di layar Android pada sesi terpisah
yang disengaja. `Stop`/`Exit` tidak membatalkan checkout yang sudah terkirim.

## Pengujian

Pemeriksaan khusus host, tanpa perangkat dan tanpa checkout:

```bash
sh -n run-linux.sh
python3 -m py_compile tui.py tui_core.py macos_runner.py ultra0.py device_selector.py
python3 -m unittest discover -s tests -p 'test_*.py'
git diff --check
```

Suite khusus Linux (semua interaksi ADB/Frida/checkout di-mock):

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_linux.py' -v
```

Perlu diketahui: `tests/test_english_only.py` menyusuri seluruh pohon dan akan memindai
`.venv` bila ada; itu keterbatasan upstream yang sudah ada sebelumnya, bukan regresi
Linux. Berkas terjemahan Indonesia ini lolos karena skrip Latin tidak termasuk rentang
yang ditolak.

## Pemecahan masalah

| Gejala | Perbaikan |
| --- | --- |
| `Could not create .venv` (keluar 2) | `sudo apt install -y python3-venv python3-pip`, atau pasang `uv` |
| `ADB is missing` (keluar 3) | `sudo apt install -y adb android-sdk-platform-tools-common`, atau set `ADB_PATH` |
| Perangkat tampil `unauthorized` | Terima **Allow USB debugging** di perangkat; `adb kill-server && adb start-server` |
| Perangkat tampil `offline` | Sambungkan ulang kabel atau jalankan ulang emulator |
| `Multiple different Android devices` (keluar 4) | Putuskan perangkat lain; tool menolak menebak |
| `Root is unavailable` | Aktifkan root untuk instance emulator; pada perangkat fisik, root harus sudah tersedia |
| `Frida 16.5.9 required` | Hapus `.venv` lalu jalankan ulang launcher, atau `uv pip install --python .venv/bin/python frida==16.5.9` |
| `Unsupported device ABI` | ABI perangkat tidak punya build resmi `frida-server` yang cocok |
| Google Play meminta verifikasi akun | Berhenti. Tinjau Keamanan Akun Google; jangan ulangi atau pakai `--force` |

## Rollback

```bash
# Hapus runtime lokal saja; berkas sumber tidak disentuh.
rm -rf .venv ultra0-report

# Hentikan pembantu di sisi Android pada perangkat (butuh root).
adb -s <serial> shell "su -c 'pkill frida-server'"
adb -s <serial> shell "rm -f /data/local/tmp/frida-server /data/local/tmp/module_521.apk"

# Kembalikan nilai proxy yang sengaja Anda ganti (periksa nilai aslinya dulu).
adb -s <serial> shell settings get global http_proxy
```

Nyalakan kembali aplikasi VPN yang sempat dihentikan paksa oleh toolkit. Untuk membatalkan
perubahan kode sepenuhnya, kembali ke `main` di fork Anda.

## Kelayakan VPS

**Terblokir / belum terverifikasi.** VPS Ubuntu tanpa layar tidak menyediakan runtime
Android yang dibutuhkan, dan pemilihan Frida upstream hanya menghitung perangkat Frida
bertipe **USB** — jadi port forwarding ADB saja **tidak** menciptakan target Frida yang
bisa dipakai.

- **Disarankan**: jalankan toolkit dan instance Android di mesin lokal yang sama, lalu
  akses mesin itu hanya dari sesi lokal atau SSH yang tepercaya.
- **Opsional**: hanya layak jika VPS menjalankan lingkungan Android khusus yang kompatibel
  (nested virtualization KVM, RAM memadai, image bersertifikat Play) atau punya terowongan
  aman terverifikasi ke perangkat resmi, dengan **ADB dan Frida sama-sama** dipetakan ke
  **instance Android yang sama**. Konfigurasi ini **belum** diuji di sini; jangan
  mengklaim dukungan tanpa benar-benar menjalankannya.

Jangan pernah membuka ADB server `5037`, ADB Android `5555`, atau Frida `27042` pada
antarmuka publik. Jangan menerbitkan dasbor web atau rute Caddy untuk tool ini. Jangan
pakai `--network host` di Docker. Jangan pakai `--privileged` di Docker. Jangan pakai USB
passthrough host sebagai jalan pintas. Ikat transport apa pun ke loopback host dan akses
lewat SSH setelah ditinjau.

## Catatan keamanan dan lisensi

- Payload bawaan `assets/modules/module_521.b64` **belum diaudit secara independen**.
  Perlakukan sebagai kode tidak tepercaya yang dapat berjalan di dalam Google Play pada
  perangkat.
- Laporan lokal tersimpan di `ultra0-report/` dan bersifat **sensitif**: bisa memuat
  alamat akun Google Play serta metadata penawaran/pembelian. `ultra0-report/`, `logs/`,
  dan artefak akun `*.json` diabaikan oleh git. Jangan pernah menempelkannya ke issue.
- Repo upstream **tidak menyatakan LICENSE untuk seluruh repo**. `THIRD_PARTY_NOTICES.md`
  mempertahankan pemberitahuan MIT asli **hanya untuk bagian yang berasal dari upstream**.
  Jangan menganggap semua kontribusi — termasuk port Linux ini — berlisensi MIT.
  Konfirmasikan dengan pemegang hak cipta sebelum mendistribusikan ulang.
- Proyek ini tidak resmi dan tidak berafiliasi dengan, tidak didukung oleh, maupun tidak
  disponsori Google, Google Play, Google One, NetEase, atau MuMuPlayer.

## Berkas yang ditambahkan port Linux

| Berkas | Fungsi |
| --- | --- |
| `run-linux.sh` | Launcher POSIX: `--help`, `--doctor`, `--check`, `--list`, `--step`, `--sequence` |
| `scripts/linux-doctor.py` | Backend inspeksi host + ADB hanya-baca untuk `--doctor` |
| `tests/test_linux.py` | Tes regresi Linux yang di-mock (routing, launcher, doctor, gerbang persetujuan) |
| `UBUNTU-SETUP.md` | Panduan ini (versi Inggris) |
| `UBUNTU-SETUP.id.md` | Berkas ini (versi Indonesia) |

Berkas yang diubah: `tui_core.py` (`NATIVE_PLATFORMS`, `is_native_platform()`, routing
`command_for_step()`) dan `tui.py` (predikat platform). Engine upstream, JavaScript
billing, dan kontrak adapter tidak berubah.
