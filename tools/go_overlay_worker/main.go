package main

import (
	"bufio"
	"bytes"
	"encoding/binary"
	"encoding/json"
	"flag"
	"io"
	"log"
	"net/http"
	"os"
	"os/exec"
	"sync"
	"sync/atomic"
	"time"
)

type statsSnapshot struct {
	ActiveClients int   `json:"active_clients"`
	PeakClients   int   `json:"peak_clients"`
	BytesOut      int64 `json:"bytes_out"`
	Closed        bool  `json:"closed"`
}

type relay struct {
	contentType string
	streamPath  string

	mu       sync.Mutex
	clients  map[int]chan []byte
	nextID   int
	closed   bool
	active   int32
	peak     int32
	bytesOut int64
}

func newRelay(contentType, streamPath string) *relay {
	return &relay{
		contentType: contentType,
		streamPath:  streamPath,
		clients:     map[int]chan []byte{},
	}
}

func (r *relay) register() (int, chan []byte, bool) {
	r.mu.Lock()
	defer r.mu.Unlock()
	if r.closed {
		return 0, nil, false
	}
	id := r.nextID
	r.nextID++
	ch := make(chan []byte, 128)
	r.clients[id] = ch
	active := atomic.AddInt32(&r.active, 1)
	for {
		peak := atomic.LoadInt32(&r.peak)
		if active <= peak || atomic.CompareAndSwapInt32(&r.peak, peak, active) {
			break
		}
	}
	return id, ch, true
}

func (r *relay) unregister(id int) {
	r.mu.Lock()
	ch, ok := r.clients[id]
	if ok {
		delete(r.clients, id)
	}
	r.mu.Unlock()
	if ok {
		close(ch)
		atomic.AddInt32(&r.active, -1)
	}
}

func (r *relay) close() {
	r.mu.Lock()
	defer r.mu.Unlock()
	if r.closed {
		return
	}
	r.closed = true
	for id, ch := range r.clients {
		delete(r.clients, id)
		close(ch)
	}
	atomic.StoreInt32(&r.active, 0)
}

func (r *relay) publish(chunk []byte) {
	if len(chunk) == 0 {
		return
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	if r.closed {
		return
	}
	for id, ch := range r.clients {
		select {
		case ch <- chunk:
		default:
			delete(r.clients, id)
			close(ch)
			atomic.AddInt32(&r.active, -1)
		}
	}
}

func (r *relay) stats() statsSnapshot {
	r.mu.Lock()
	closed := r.closed
	r.mu.Unlock()
	return statsSnapshot{
		ActiveClients: int(atomic.LoadInt32(&r.active)),
		PeakClients:   int(atomic.LoadInt32(&r.peak)),
		BytesOut:      atomic.LoadInt64(&r.bytesOut),
		Closed:        closed,
	}
}

type latestFrameStore struct {
	mu    sync.RWMutex
	frame []byte
}

func (s *latestFrameStore) set(frame []byte) {
	s.mu.Lock()
	s.frame = frame
	s.mu.Unlock()
}

func (s *latestFrameStore) get() []byte {
	s.mu.RLock()
	defer s.mu.RUnlock()
	if len(s.frame) == 0 {
		return nil
	}
	out := make([]byte, len(s.frame))
	copy(out, s.frame)
	return out
}

func main() {
	listenAddr := flag.String("listen", ":8098", "listen address")
	streamPath := flag.String("stream-path", "/live.mp4", "stream path")
	contentType := flag.String("content-type", "video/mp4", "content type")
	statsPath := flag.String("stats-path", "/stats", "stats path")
	frameRate := flag.Float64("frame-rate", 3.0, "scheduler frame rate")
	ffmpegBin := flag.String("ffmpeg-bin", "ffmpeg", "ffmpeg binary")
	ffmpegArgsJSON := flag.String("ffmpeg-args-json", "[]", "json array of ffmpeg args")
	flag.Parse()

	var ffmpegArgs []string
	if err := json.Unmarshal([]byte(*ffmpegArgsJSON), &ffmpegArgs); err != nil {
		log.Fatalf("invalid ffmpeg args json: %v", err)
	}

	cmd := exec.Command(*ffmpegBin, ffmpegArgs...)
	ffmpegIn, err := cmd.StdinPipe()
	if err != nil {
		log.Fatal(err)
	}
	ffmpegOut, err := cmd.StdoutPipe()
	if err != nil {
		log.Fatal(err)
	}
	ffmpegErr, err := cmd.StderrPipe()
	if err != nil {
		log.Fatal(err)
	}
	if err := cmd.Start(); err != nil {
		log.Fatal(err)
	}

	relayState := newRelay(*contentType, *streamPath)
	store := &latestFrameStore{}
	done := make(chan struct{})

	go func() {
		defer close(done)
		reader := bufio.NewReader(os.Stdin)
		for {
			var length uint32
			if err := binary.Read(reader, binary.BigEndian, &length); err != nil {
				if err != io.EOF {
					log.Printf("frame read header error: %v", err)
				}
				_ = ffmpegIn.Close()
				return
			}
			if length == 0 {
				continue
			}
			buf := make([]byte, length)
			if _, err := io.ReadFull(reader, buf); err != nil {
				log.Printf("frame read payload error: %v", err)
				_ = ffmpegIn.Close()
				return
			}
			store.set(buf)
		}
	}()

	go func() {
		ticker := time.NewTicker(time.Duration(float64(time.Second) / *frameRate))
		defer ticker.Stop()
		for {
			select {
			case <-done:
				return
			case <-ticker.C:
				frame := store.get()
				if len(frame) == 0 {
					continue
				}
				if _, err := io.Copy(ffmpegIn, bytes.NewReader(frame)); err != nil {
					return
				}
			}
		}
	}()

	go func() {
		buf := make([]byte, 32768)
		for {
			n, err := ffmpegOut.Read(buf)
			if n > 0 {
				chunk := make([]byte, n)
				copy(chunk, buf[:n])
				relayState.publish(chunk)
			}
			if err != nil {
				relayState.close()
				return
			}
		}
	}()

	go func() {
		_, _ = io.Copy(os.Stderr, ffmpegErr)
	}()

	mux := http.NewServeMux()
	mux.HandleFunc(*streamPath, func(w http.ResponseWriter, req *http.Request) {
		id, ch, ok := relayState.register()
		if !ok {
			http.Error(w, "relay closed", http.StatusServiceUnavailable)
			return
		}
		defer relayState.unregister(id)
		w.Header().Set("Content-Type", relayState.contentType)
		w.Header().Set("Connection", "keep-alive")
		w.WriteHeader(http.StatusOK)
		flusher, _ := w.(http.Flusher)
		for chunk := range ch {
			if _, err := w.Write(chunk); err != nil {
				return
			}
			atomic.AddInt64(&relayState.bytesOut, int64(len(chunk)))
			if flusher != nil {
				flusher.Flush()
			}
		}
	})
	mux.HandleFunc(*statsPath, func(w http.ResponseWriter, req *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(relayState.stats())
	})

	server := &http.Server{Addr: *listenAddr, Handler: mux}
	go func() {
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatal(err)
		}
	}()

	err = cmd.Wait()
	relayState.close()
	if err != nil {
		log.Printf("ffmpeg exited: %v", err)
	}
}
