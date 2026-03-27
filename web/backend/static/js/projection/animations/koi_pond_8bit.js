// Koi Pond 8-bit Animation - internal canvas port inspired by looping pixel koi pond GIF backgrounds
class KoiPond8BitAnimation extends BaseAnimation {
    setup() {
        this.time = 0;
        this.pixelSize = Math.max(6, Math.round(Math.min(this.canvas.width, this.canvas.height) / 48));
        this.koi = Array.from({ length: 6 }, (_, index) => ({
            phase: index / 6,
            lane: index % 3,
            speed: 0.000022 + index * 0.000002,
            size: 1 + (index % 2) * 0.22,
            colorA: ['#f6a11a', '#f05e23', '#fff2d8'][index % 3],
            colorB: ['#fff2d8', '#2a2220', '#f05e23'][index % 3],
        }));
        this.waveGain = 1;
    }

    fillPixelRect(x, y, w, h, color) {
        this.ctx.fillStyle = color;
        this.ctx.fillRect(
            Math.round(x / this.pixelSize) * this.pixelSize,
            Math.round(y / this.pixelSize) * this.pixelSize,
            Math.ceil(w / this.pixelSize) * this.pixelSize,
            Math.ceil(h / this.pixelSize) * this.pixelSize
        );
    }

    drawBackground() {
        const cols = Math.ceil(this.canvas.width / this.pixelSize);
        const rows = Math.ceil(this.canvas.height / this.pixelSize);
        const palette = ['#122f52', '#1a4773', '#235886', '#2b6795'];

        for (let row = 0; row < rows; row++) {
            for (let col = 0; col < cols; col++) {
                const noise = Math.sin(col * 0.85 + this.time * 0.002) + Math.cos(row * 0.72 + this.time * 0.0016);
                const shade = palette[(Math.abs(Math.round(noise * 1.5 + row * 0.15 + col * 0.08)) % palette.length)];
                this.fillPixelRect(col * this.pixelSize, row * this.pixelSize, this.pixelSize, this.pixelSize, shade);
            }
        }

        for (let stripe = 0; stripe < 5; stripe++) {
            const y = this.canvas.height * (0.12 + stripe * 0.16);
            for (let x = 0; x < this.canvas.width; x += this.pixelSize * 2) {
                const wave = Math.sin(x * 0.018 + this.time * 0.003 + stripe) * (this.pixelSize * 0.9 * this.waveGain);
                this.fillPixelRect(x, y + wave, this.pixelSize * 2, this.pixelSize, 'rgba(200, 236, 255, 0.24)');
            }
        }

        const lilyPads = [
            [0.16, 0.24, 1.1],
            [0.76, 0.18, 0.9],
            [0.2, 0.72, 1.2],
            [0.82, 0.68, 1.05],
        ];
        lilyPads.forEach(([nx, ny, scale], index) => {
            const x = this.canvas.width * nx + Math.sin(this.time * 0.0012 + index) * this.pixelSize;
            const y = this.canvas.height * ny + Math.cos(this.time * 0.001 + index) * this.pixelSize;
            const size = this.pixelSize * 5 * scale;
            this.fillPixelRect(x - size * 0.5, y - size * 0.35, size, size * 0.7, '#3c8c4d');
            this.fillPixelRect(x - size * 0.18, y - size * 0.18, size * 0.36, size * 0.16, '#57b468');
        });
    }

    drawKoi(fish, index) {
        const t = (this.time * fish.speed + fish.phase) % 1;
        const pathX = this.canvas.width * (0.08 + 0.84 * t);
        const laneY = this.canvas.height * (0.24 + fish.lane * 0.22);
        const pathY = laneY + Math.sin(this.time * 0.0022 + index * 1.4 + t * Math.PI * 2) * this.canvas.height * 0.06;
        const dir = Math.sin(this.time * fish.speed * 40 + index) >= 0 ? 1 : -1;
        const unit = this.pixelSize * fish.size;

        this.ctx.save();
        this.ctx.translate(pathX, pathY);
        this.ctx.scale(dir, 1);

        this.fillPixelRect(-4 * unit, -1 * unit, 5 * unit, 2 * unit, fish.colorA);
        this.fillPixelRect(-2 * unit, -2 * unit, 3 * unit, 1 * unit, fish.colorA);
        this.fillPixelRect(-1 * unit, 1 * unit, 2 * unit, 1 * unit, fish.colorA);
        this.fillPixelRect(1 * unit, -1 * unit, 1 * unit, 1 * unit, fish.colorB);
        this.fillPixelRect(-3 * unit, -1 * unit, 1 * unit, 1 * unit, fish.colorB);
        this.fillPixelRect(-5 * unit, -1 * unit, 1 * unit, 1 * unit, fish.colorB);
        this.fillPixelRect(-6 * unit, -2 * unit, 2 * unit, 1 * unit, fish.colorA);
        this.fillPixelRect(-6 * unit, 1 * unit, 2 * unit, 1 * unit, fish.colorA);
        this.fillPixelRect(2 * unit, -1 * unit, 1 * unit, 1 * unit, '#171312');

        this.fillPixelRect(-1 * unit, -3 * unit, 1 * unit, 1 * unit, 'rgba(255,255,255,0.35)');
        this.fillPixelRect(-2 * unit, 2 * unit, 1 * unit, 1 * unit, 'rgba(255,255,255,0.22)');

        this.ctx.restore();
    }

    draw() {
        this.time += 16;
        this.drawBackground();
        this.koi.forEach((fish, index) => this.drawKoi(fish, index));
    }

    onDataUpdate() {
        if (this.data.weather) {
            const wind = Number(this.data.weather.windSpeed || 0);
            this.waveGain = 1 + Math.min(1.2, wind / 12);
        }
    }
}
