#!/usr/bin/env python3
from http.server import HTTPServer, BaseHTTPRequestHandler
import subprocess, json, logging, ipaddress, os

logging.basicConfig(
    filename='/var/log/ip-blocker.log',
    level=logging.INFO,
    format='%(asctime)s %(message)s'
)

IPTABLES      = '/usr/sbin/iptables'
BLOCKED_FILE  = '/etc/iptables/blocked-ips'
ISOLATED_FILE = '/etc/iptables/isolated-hosts'
TAILSCALE_NET = ipaddress.ip_network('100.64.0.0/10')
WAZUH_MANAGER = '100.69.87.17'

def is_tailscale(ip):
    try:
        return ipaddress.ip_address(ip) in TAILSCALE_NET
    except ValueError:
        return False

def rule_exists(chain, ip):
    r = subprocess.run(
        [IPTABLES, '-C', chain, '-s', ip, '-j', 'DROP'],
        capture_output=True
    )
    if r.returncode == 0:
        return True
    if is_tailscale(ip):
        r2 = subprocess.run(
            [IPTABLES, '-C', chain, '-i', 'tailscale0', '-s', ip, '-j', 'DROP'],
            capture_output=True
        )
        return r2.returncode == 0
    return False

def is_isolated():
    return os.path.exists(ISOLATED_FILE)

def run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logging.error(f'CMD FAILED: {" ".join(cmd)} | {result.stderr.strip()}')
        return False
    return True

def add_to_blocked_file(ip):
    try:
        os.makedirs(os.path.dirname(BLOCKED_FILE), exist_ok=True)
        with open(BLOCKED_FILE, 'a+') as f:
            f.seek(0)
            if ip not in f.read().splitlines():
                f.write(ip + '\n')
    except Exception as e:
        logging.error(f'Failed to write {ip} to {BLOCKED_FILE}: {e}')

def remove_from_blocked_file(ip):
    try:
        if not os.path.exists(BLOCKED_FILE):
            return
        with open(BLOCKED_FILE, 'r') as f:
            lines = f.read().splitlines()
        lines = [l for l in lines if l.strip() != ip]
        with open(BLOCKED_FILE, 'w') as f:
            f.write('\n'.join(lines) + ('\n' if lines else ''))
    except Exception as e:
        logging.error(f'Failed to remove {ip} from {BLOCKED_FILE}: {e}')

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            body   = json.loads(self.rfile.read(length))
            ip     = body.get('ip', '').strip()
            action = body.get('action', 'block')

            if not ip and action not in ('isolate', 'unisolate'):
                self.send_response(400); self.end_headers()
                self.wfile.write(b'{"error":"missing ip"}'); return

            if action == 'block':
                if rule_exists('INPUT', ip):
                    logging.info(f'ALREADY BLOCKED {ip} — skipping duplicate')
                    self.send_response(200); self.end_headers()
                    self.wfile.write(json.dumps({"status":"already_blocked","ip":ip}).encode())
                    return
                ok1 = run([IPTABLES, '-I', 'FORWARD', '1', '-s', ip, '-j', 'DROP'])
                ok2 = run([IPTABLES, '-I', 'INPUT',   '1', '-s', ip, '-j', 'DROP'])
                add_to_blocked_file(ip)
                if ok1 and ok2:
                    via = 'tailscale0' if is_tailscale(ip) else 'eth0'
                    logging.info(f'BLOCKED {ip} via {via}')
                    self.send_response(200); self.end_headers()
                    self.wfile.write(json.dumps({"status":"blocked","ip":ip}).encode())
                else:
                    logging.error(f'BLOCK FAILED for {ip}')
                    self.send_response(500); self.end_headers()
                    self.wfile.write(json.dumps({"status":"failed","ip":ip}).encode())

            elif action == 'unblock':
                while run([IPTABLES, '-D', 'INPUT',   '-s', ip, '-j', 'DROP']): pass
                while run([IPTABLES, '-D', 'FORWARD', '-s', ip, '-j', 'DROP']): pass
                if is_tailscale(ip):
                    while run([IPTABLES, '-D', 'INPUT',   '-i', 'tailscale0', '-s', ip, '-j', 'DROP']): pass
                    while run([IPTABLES, '-D', 'FORWARD', '-i', 'tailscale0', '-s', ip, '-j', 'DROP']): pass
                remove_from_blocked_file(ip)
                logging.info(f'UNBLOCKED {ip}')
                self.send_response(200); self.end_headers()
                self.wfile.write(json.dumps({"status":"unblocked","ip":ip}).encode())

            elif action == 'isolate':
                agent = body.get('agent', 'unknown')
                if is_isolated():
                    logging.info(f'HOST ALREADY ISOLATED — skipping')
                    self.send_response(200); self.end_headers()
                    self.wfile.write(json.dumps({"status":"already_isolated"}).encode())
                    return
                errors = []

                # Step 1 — Flush existing INPUT and FORWARD rules
                run([IPTABLES, '-F', 'INPUT'])
                run([IPTABLES, '-F', 'FORWARD'])

                # Step 2 — Allow already-established connections (prevent OS network crash)
                run([IPTABLES, '-I', 'INPUT',  '1', '-m', 'conntrack', '--ctstate', 'ESTABLISHED,RELATED', '-j', 'ACCEPT'])
                run([IPTABLES, '-I', 'OUTPUT', '1', '-m', 'conntrack', '--ctstate', 'ESTABLISHED,RELATED', '-j', 'ACCEPT'])

                # Step 3 — Wazuh Manager lifeboat (keeps agent visible in dashboard)
                ok_wm1 = run([IPTABLES, '-I', 'INPUT',  '2', '-s', WAZUH_MANAGER, '-j', 'ACCEPT'])
                ok_wm2 = run([IPTABLES, '-I', 'OUTPUT', '2', '-d', WAZUH_MANAGER, '-j', 'ACCEPT'])
                if not ok_wm1 or not ok_wm2:
                    errors.append('Failed to add Wazuh manager ACCEPT rule')

                # Step 4 — Tailscale survival pack (keeps Tailscale mesh alive for remote deisolation)
                # Tailscale peer-to-peer mesh uses UDP 41641
                run([IPTABLES, '-I', 'INPUT',  '3', '-p', 'udp', '--dport', '41641', '-j', 'ACCEPT'])
                run([IPTABLES, '-I', 'OUTPUT', '3', '-p', 'udp', '--dport', '41641', '-j', 'ACCEPT'])
                # Tailscale control plane uses outbound HTTPS (443)
                run([IPTABLES, '-I', 'OUTPUT', '4', '-p', 'tcp', '--dport', '443',   '-j', 'ACCEPT'])
                run([IPTABLES, '-I', 'INPUT',  '4', '-p', 'tcp', '--sport', '443',   '-j', 'ACCEPT'])
                # Allow DNS so Tailscale can resolve coordination servers
                run([IPTABLES, '-I', 'OUTPUT', '5', '-p', 'udp', '--dport', '53',    '-j', 'ACCEPT'])
                run([IPTABLES, '-I', 'INPUT',  '5', '-p', 'udp', '--sport', '53',    '-j', 'ACCEPT'])
                # Allow blocker.py port 9999 so n8n can send unisolate command via Tailscale
                run([IPTABLES, '-I', 'INPUT',  '6', '-p', 'tcp', '--dport', '9999',  '-j', 'ACCEPT'])

                # Step 5 — Loopback (localhost must always work)
                run([IPTABLES, '-I', 'INPUT',  '7', '-i', 'lo', '-j', 'ACCEPT'])
                run([IPTABLES, '-I', 'OUTPUT', '7', '-o', 'lo', '-j', 'ACCEPT'])

                # Step 6 — Drop everything else (the actual isolation)
                ok_d1 = run([IPTABLES, '-P', 'INPUT',   'DROP'])
                ok_d2 = run([IPTABLES, '-P', 'FORWARD', 'DROP'])
                ok_d3 = run([IPTABLES, '-P', 'OUTPUT',  'DROP'])
                if not ok_d1 or not ok_d2 or not ok_d3:
                    errors.append('Failed to set DROP policy')

                # Step 7 — Write isolation marker file
                try:
                    import datetime
                    os.makedirs(os.path.dirname(ISOLATED_FILE), exist_ok=True)
                    with open(ISOLATED_FILE, 'w') as f:
                        f.write(json.dumps({
                            "agent": agent,
                            "isolated_at": datetime.datetime.utcnow().isoformat(),
                            "triggered_by_ip": ip or "n8n"
                        }))
                except Exception as e:
                    errors.append(f'Failed to write isolation marker: {e}')

                if errors:
                    logging.error(f'ISOLATE PARTIAL FAILURE: {errors}')
                    self.send_response(207); self.end_headers()
                    self.wfile.write(json.dumps({"status":"partially_isolated","agent":agent,"errors":errors}).encode())
                else:
                    logging.info(f'HOST ISOLATED — agent:{agent} triggered_by:{ip}')
                    self.send_response(200); self.end_headers()
                    self.wfile.write(json.dumps({"status":"isolated","agent":agent}).encode())

            elif action == 'unisolate':
                # Reset all policies back to ACCEPT
                run([IPTABLES, '-P', 'INPUT',   'ACCEPT'])
                run([IPTABLES, '-P', 'FORWARD', 'ACCEPT'])
                run([IPTABLES, '-P', 'OUTPUT',  'ACCEPT'])
                # Flush all rules
                run([IPTABLES, '-F', 'INPUT'])
                run([IPTABLES, '-F', 'OUTPUT'])
                run([IPTABLES, '-F', 'FORWARD'])
                # Remove isolation marker
                try:
                    if os.path.exists(ISOLATED_FILE):
                        os.remove(ISOLATED_FILE)
                except Exception as e:
                    logging.error(f'Failed to remove isolation marker: {e}')
                # Re-apply any previously blocked attacker IPs
                if os.path.exists(BLOCKED_FILE):
                    with open(BLOCKED_FILE) as f:
                        for blocked_ip in f.read().splitlines():
                            if blocked_ip.strip():
                                run([IPTABLES, '-I', 'INPUT',   '1', '-s', blocked_ip, '-j', 'DROP'])
                                run([IPTABLES, '-I', 'FORWARD', '1', '-s', blocked_ip, '-j', 'DROP'])
                logging.info(f'HOST UNISOLATED — normal policy restored')
                self.send_response(200); self.end_headers()
                self.wfile.write(json.dumps({"status":"unisolated"}).encode())

            else:
                self.send_response(400); self.end_headers()
                self.wfile.write(b'{"error":"unknown action"}')

        except Exception as e:
            logging.error(f'Exception: {e}')
            self.send_response(500); self.end_headers()
            self.wfile.write(json.dumps({"error":str(e)}).encode())

    def log_message(self, f, *a): pass

HTTPServer(('0.0.0.0', 9999), Handler).serve_forever()
