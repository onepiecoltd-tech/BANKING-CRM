//go:build windows

package main

import (
	"bufio"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"syscall"
	"time"
)

const (
	apiPort = "8000"
	webPort = "8080"
)

var base string

func say(f string, a ...any) { fmt.Printf(f+"\n", a...) }

func fail(f string, a ...any) {
	say("\n[LỖI] "+f, a...)
	say("\nNhấn Enter để thoát...")
	bufio.NewReader(os.Stdin).ReadString('\n')
	os.Exit(1)
}

func hidden(c *exec.Cmd) *exec.Cmd {
	c.SysProcAttr = &syscall.SysProcAttr{HideWindow: true, CreationFlags: 0x08000000}
	return c
}

// run executes a command, streaming output to console (used for setup steps).
func run(dir string, name string, args ...string) error {
	c := exec.Command(name, args...)
	c.Dir = dir
	c.Stdout, c.Stderr = os.Stdout, os.Stderr
	return c.Run()
}

func portOpen(p string) bool {
	c, err := net.DialTimeout("tcp", "127.0.0.1:"+p, 500*time.Millisecond)
	if err != nil {
		return false
	}
	c.Close()
	return true
}

// pidOnPort returns the PID listening on 127.0.0.1:<port> (0 if none).
func pidOnPort(p string) int {
	out, err := hidden(exec.Command("netstat", "-ano", "-p", "tcp")).Output()
	if err != nil {
		return 0
	}
	for _, ln := range strings.Split(string(out), "\n") {
		f := strings.Fields(ln)
		if len(f) >= 5 && strings.EqualFold(f[0], "TCP") &&
			strings.HasSuffix(f[1], ":"+p) && strings.HasSuffix(f[2], ":0") {
			if pid, e := strconv.Atoi(f[4]); e == nil && pid > 0 {
				return pid
			}
		}
	}
	return 0
}

func procName(pid int) string {
	out, err := hidden(exec.Command("tasklist", "/FI", "PID eq "+strconv.Itoa(pid), "/FO", "CSV", "/NH")).Output()
	if err != nil {
		return ""
	}
	f := strings.Split(strings.TrimSpace(string(out)), ",")
	if len(f) > 0 {
		return strings.ToLower(strings.Trim(f[0], "\" "))
	}
	return ""
}

// freePort stops a stale python/node server left from a previous run so the
// new code is always the one being served. Any other program is left alone.
func freePort(p string) {
	for i := 0; i < 3; i++ {
		pid := pidOnPort(p)
		if pid == 0 {
			return
		}
		n := procName(pid)
		if n == "python.exe" || n == "pythonw.exe" || n == "node.exe" {
			say("Cổng %s đang bị bản CRM cũ chiếm (%s, PID %d) — đang tắt để chạy bản mới...", p, n, pid)
			hidden(exec.Command("taskkill", "/T", "/F", "/PID", strconv.Itoa(pid))).Run()
			time.Sleep(1500 * time.Millisecond)
			continue
		}
		fail("Cổng %s đang bị chương trình khác (%s) chiếm. Hãy tắt nó rồi chạy lại.", p, n)
	}
}

func waitPort(p string, d time.Duration) bool {
	end := time.Now().Add(d)
	for time.Now().Before(end) {
		if portOpen(p) {
			return true
		}
		time.Sleep(700 * time.Millisecond)
	}
	return false
}

var verRe = regexp.MustCompile(`Python (\d+)\.(\d+)`)

// findPython returns a command prefix for Python 3.11 or 3.12.
func findPython() []string {
	cands := [][]string{{"py", "-3.12"}, {"py", "-3.11"}, {"python3.12"}, {"python3.11"}, {"python"}}
	for _, c := range cands {
		out, err := exec.Command(c[0], append(c[1:], "--version")...).CombinedOutput()
		if err != nil {
			continue
		}
		m := verRe.FindStringSubmatch(string(out))
		if m == nil {
			continue
		}
		maj, _ := strconv.Atoi(m[1])
		min, _ := strconv.Atoi(m[2])
		if maj == 3 && (min == 11 || min == 12) {
			return c
		}
	}
	return nil
}

// flushInput discards keystrokes typed during setup so a stray Enter cannot shut CRM down.
func flushInput() {
	k := syscall.NewLazyDLL("kernel32.dll")
	k.NewProc("FlushConsoleInputBuffer").Call(uintptr(syscall.Stdin))
}

func reqHash(backend string) string {
	b, err := os.ReadFile(filepath.Join(backend, "requirements.txt"))
	if err != nil {
		return ""
	}
	h := sha256.Sum256([]byte(strings.ReplaceAll(string(b), "\r\n", "\n")))
	return hex.EncodeToString(h[:])
}

func reqMarker(backend string) string { return filepath.Join(backend, ".venv", ".req_hash") }

// reqChanged: true khi requirements.txt khác với lần cài gần nhất (hoặc venv cũ chưa có dấu).
func reqChanged(backend string) bool {
	old, err := os.ReadFile(reqMarker(backend))
	return err != nil || strings.TrimSpace(string(old)) != reqHash(backend)
}

func writeReqHash(backend string) { os.WriteFile(reqMarker(backend), []byte(reqHash(backend)), 0644) }

func exists(p string) bool { _, err := os.Stat(p); return err == nil }

func main() {
	exe, _ := os.Executable()
	base = filepath.Dir(exe)
	backend := filepath.Join(base, "backend")
	frontend := filepath.Join(base, "frontend")
	if !exists(backend) || !exists(frontend) {
		fail("Không thấy thư mục backend/frontend cạnh CRM.exe (%s). Hãy để CRM.exe trong thư mục CRM.", base)
	}
	say("=== BankRM AI — CRM launcher ===")

	// ---- Backend setup ----
	venvPy := filepath.Join(backend, ".venv", "Scripts", "python.exe")
	if !exists(venvPy) {
		py := findPython()
		if py == nil {
			fail("Cần Python 3.11 hoặc 3.12 (3.13 không được hỗ trợ). Cài từ python.org rồi chạy lại.")
		}
		say("[1/4] Tạo môi trường Python (.venv)...")
		if err := run(backend, py[0], append(py[1:], "-m", "venv", ".venv")...); err != nil {
			fail("Tạo venv thất bại: %v", err)
		}
		say("[1/4] Cài thư viện backend (lần đầu mất vài phút)...")
		if err := run(backend, venvPy, "-m", "pip", "install", "-r", "requirements.txt"); err != nil {
			os.RemoveAll(filepath.Join(backend, ".venv"))
			fail("pip install thất bại: %v", err)
		}
		writeReqHash(backend)
	} else if reqChanged(backend) {
		say("[1/4] requirements.txt đã thay đổi — cập nhật thư viện backend (có thể mất vài phút)...")
		if err := run(backend, venvPy, "-m", "pip", "install", "-r", "requirements.txt"); err != nil {
			fail("pip install thất bại: %v", err)
		}
		writeReqHash(backend)
	} else {
		say("[1/4] Môi trường Python: OK")
	}

	envFile := filepath.Join(backend, ".env")
	if !exists(envFile) {
		data, err := os.ReadFile(filepath.Join(backend, ".env.example"))
		if err == nil {
			s := strings.ReplaceAll(string(data), "\r\n", "\n")
			s = regexp.MustCompile(`(?m)^SENDER_BACKEND=.*$`).ReplaceAllString(s, "SENDER_BACKEND=mock")
			s = regexp.MustCompile(`(?m)^LLM_BACKEND=.*$`).ReplaceAllString(s, "LLM_BACKEND=gemini")
			os.WriteFile(envFile, []byte(s), 0644)
			say("[2/4] Đã tạo backend\\.env — hãy điền GEMINI_API_KEY rồi chạy lại để agent dùng Gemini.")
			exec.Command("notepad.exe", envFile).Start()
		}
	} else {
		say("[2/4] File .env: OK")
	}

	if !exists(filepath.Join(backend, "banking_crm.db")) {
		say("[3/4] Tạo dữ liệu mẫu (500 khách hàng)...")
		if err := run(backend, venvPy, filepath.Join("data", "seed_db.py")); err != nil {
			fail("Seed DB thất bại: %v", err)
		}
	} else {
		say("[3/4] Database: OK")
	}

	// ---- Frontend setup ----
	if _, err := exec.LookPath("npm.cmd"); err != nil {
		fail("Chưa cài Node.js (cần 18+). Cài từ nodejs.org rồi chạy lại.")
	}
	if !exists(filepath.Join(frontend, "node_modules")) {
		say("[4/4] Cài thư viện frontend (npm ci, lần đầu mất vài phút)...")
		if err := run(frontend, "npm.cmd", "ci"); err != nil {
			fail("npm ci thất bại: %v", err)
		}
	} else {
		say("[4/4] Thư viện frontend: OK")
	}

	// ---- Start services ----
	logs := filepath.Join(base, "logs")
	os.MkdirAll(logs, 0755)
	var procs []*exec.Cmd

	freePort(apiPort)
	freePort(webPort)
	{
		lf, _ := os.Create(filepath.Join(logs, "backend.log"))
		c := hidden(exec.Command(venvPy, "-m", "uvicorn", "src.api:app", "--host", "127.0.0.1", "--port", apiPort))
		c.Dir = backend
		c.Stdout, c.Stderr = lf, lf
		if err := c.Start(); err != nil {
			fail("Không chạy được backend: %v", err)
		}
		procs = append(procs, c)
	}
	{
		lf, _ := os.Create(filepath.Join(logs, "frontend.log"))
		c := hidden(exec.Command("npm.cmd", "run", "dev", "--", "--host", "127.0.0.1"))
		c.Dir = frontend
		c.Stdout, c.Stderr = lf, lf
		if err := c.Start(); err != nil {
			fail("Không chạy được frontend: %v", err)
		}
		procs = append(procs, c)
	}

	say("\nĐang khởi động dịch vụ...")
	if !waitPort(apiPort, 90*time.Second) {
		fail("Backend không lên sau 90s. Xem logs\\backend.log")
	}
	if !waitPort(webPort, 90*time.Second) {
		fail("Frontend không lên sau 90s. Xem logs\\frontend.log")
	}
	url := "http://127.0.0.1:" + webPort
	say("Sẵn sàng: %s  (API: http://127.0.0.1:%s/docs)", url, apiPort)
	exec.Command("rundll32", "url.dll,FileProtocolHandler", url).Start()

	say("\nCRM đang chạy. Giữ cửa sổ này mở. Gõ q rồi Enter để TẮT CRM.")
	flushInput()
	rd := bufio.NewReader(os.Stdin)
	for {
		line, err := rd.ReadString('\n')
		if strings.EqualFold(strings.TrimSpace(line), "q") || err != nil {
			break
		}
		say("(Gõ q rồi Enter để tắt)")
	}
	for _, p := range procs {
		exec.Command("taskkill", "/T", "/F", "/PID", strconv.Itoa(p.Process.Pid)).Run()
	}
	say("Đã tắt.")
}
