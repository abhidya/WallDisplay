// Koi Fish Animation - internal canvas port inspired by CSS koi fish studies
class KoiFishAnimation extends BaseAnimation {
    setup() {
        this.time = 0;
        this.fish = [
            {
                phase: 0,
                speed: 0.00003,
                size: 0.18,
                body: '#f06b2d',
                accent: '#fff6e8',
                pathScaleX: 0.34,
                pathScaleY: 0.28,
            },
            {
                phase: 0.5,
                speed: 0.000024,
                size: 0.16,
                body: '#f4f0ea',
                accent: '#ef6a31',
                pathScaleX: 0.29,
                pathScaleY: 0.24,
            },
        ];
        this.waterShift = 0;
        this.windInfluence = 0;
    }

    computePoint(t, fishIndex) {
        const fish = this.fish[fishIndex];
        const a = this.time * fish.speed + fish.phase + t;
        const cx = this.canvas.width * 0.5;
        const cy = this.canvas.height * 0.5;
        const x = cx + Math.cos(a * Math.PI * 2) * this.canvas.width * fish.pathScaleX
            + Math.sin(a * Math.PI * 4) * this.canvas.width * 0.08;
        const y = cy + Math.sin(a * Math.PI * 2) * this.canvas.height * fish.pathScaleY
            + Math.cos(a * Math.PI * 3) * this.canvas.height * 0.06;
        return { x, y };
    }

    drawFish(index) {
        const fish = this.fish[index];
        const segments = 15;
        const head = this.computePoint(0, index);
        const neck = this.computePoint(0.0125, index);
        const angle = Math.atan2(neck.y - head.y, neck.x - head.x);

        for (let segment = segments - 1; segment >= 0; segment--) {
            const progress = segment / (segments - 1);
            const point = this.computePoint(progress * 0.12, index);
            const radius = fish.size * this.canvas.height * (1 - progress * 0.6) * (0.55 + Math.sin(progress * Math.PI) * 0.55);

            this.ctx.save();
            this.ctx.translate(point.x, point.y);
            this.ctx.rotate(angle + Math.sin(this.time * 0.003 + progress * 8 + index) * 0.08);

            const fill = this.ctx.createRadialGradient(-radius * 0.25, -radius * 0.25, radius * 0.1, 0, 0, radius);
            fill.addColorStop(0, fish.accent);
            fill.addColorStop(0.45, fish.body);
            fill.addColorStop(1, 'rgba(80, 26, 12, 0.2)');
            this.ctx.fillStyle = fill;
            this.ctx.beginPath();
            this.ctx.ellipse(0, 0, radius, radius * 0.72, 0, 0, Math.PI * 2);
            this.ctx.fill();

            if (segment === 0) {
                this.ctx.fillStyle = '#101010';
                this.ctx.beginPath();
                this.ctx.arc(radius * 0.32, -radius * 0.1, Math.max(1.5, radius * 0.08), 0, Math.PI * 2);
                this.ctx.fill();
            }

            if (segment > segments - 4) {
                this.ctx.fillStyle = fish.accent;
                this.ctx.beginPath();
                this.ctx.moveTo(-radius * 0.6, 0);
                this.ctx.quadraticCurveTo(-radius * 1.4, radius * 0.6, -radius * 1.9, 0);
                this.ctx.quadraticCurveTo(-radius * 1.4, -radius * 0.6, -radius * 0.6, 0);
                this.ctx.fill();
            }

            this.ctx.restore();
        }
    }

    draw() {
        this.time += 16;
        this.waterShift += 0.003 + this.windInfluence * 0.002;

        const gradient = this.ctx.createLinearGradient(0, 0, 0, this.canvas.height);
        gradient.addColorStop(0, '#97d9f5');
        gradient.addColorStop(1, '#2a80a8');
        this.ctx.fillStyle = gradient;
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

        for (let i = 0; i < 4; i++) {
            const y = this.canvas.height * (0.18 + i * 0.18);
            this.ctx.strokeStyle = `rgba(255,255,255,${0.08 - i * 0.01})`;
            this.ctx.lineWidth = 10 - i * 1.5;
            this.ctx.beginPath();
            for (let x = 0; x <= this.canvas.width; x += 18) {
                const wave = Math.sin((x / this.canvas.width) * Math.PI * 4 + this.waterShift * (1.5 + i * 0.2)) * (8 + i * 2);
                if (x === 0) {
                    this.ctx.moveTo(x, y + wave);
                } else {
                    this.ctx.lineTo(x, y + wave);
                }
            }
            this.ctx.stroke();
        }

        this.drawFish(0);
        this.drawFish(1);
    }

    onDataUpdate() {
        if (this.data.weather) {
            const wind = Number(this.data.weather.windSpeed || 0);
            this.windInfluence = Math.max(0, Math.min(1.5, wind / 20));
        }
    }
}

if (typeof window !== 'undefined') {
    window.KoiFishAnimation = KoiFishAnimation;
}
