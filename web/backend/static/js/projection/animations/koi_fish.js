// Koi Fish Animation - source-faithful canvas port of the segmented CSS koi pair
class KoiFishAnimation extends BaseAnimation {
    setup() {
        this.time = 0;
        this.coilCount = 15;
        this.windInfluence = 0;
        this.fishes = [
            {
                phase: 0,
                body: '#f05e23',
                accent: '#ffffff',
                shadow: 'rgba(0, 0, 0, 0.26)',
                mirrored: false,
                pathScaleX: 0.37,
                pathScaleY: 0.28,
            },
            {
                phase: 0.5,
                body: '#ffffff',
                accent: '#f05e23',
                shadow: 'rgba(0, 0, 0, 0.22)',
                mirrored: true,
                pathScaleX: 0.34,
                pathScaleY: 0.25,
            },
        ];
        this.segmentScales = [1, 1.2, 1.35, 1.55, 1.75, 1.9, 2, 2, 2, 1.9, 1.75, 1.55, 1.35, 1.2, 1];
    }

    getPathPoint(fish, t) {
        const a = this.time * 0.00006 + fish.phase + t;
        const cx = this.canvas.width * 0.5;
        const cy = this.canvas.height * 0.5;
        return {
            x: cx + Math.cos(a * Math.PI * 2) * this.canvas.width * fish.pathScaleX
                + Math.sin(a * Math.PI * 4.2) * this.canvas.width * 0.08,
            y: cy + Math.sin(a * Math.PI * 2) * this.canvas.height * fish.pathScaleY
                + Math.cos(a * Math.PI * 3.1) * this.canvas.height * 0.07,
        };
    }

    drawTail(point, angle, radius, fish) {
        this.ctx.save();
        this.ctx.translate(point.x, point.y);
        this.ctx.rotate(angle);
        this.ctx.fillStyle = fish.accent;
        this.ctx.beginPath();
        this.ctx.moveTo(-radius * 0.8, 0);
        this.ctx.quadraticCurveTo(-radius * 2.2, radius * 0.85, -radius * 3.1, 0);
        this.ctx.quadraticCurveTo(-radius * 2.2, -radius * 0.85, -radius * 0.8, 0);
        this.ctx.fill();
        this.ctx.restore();
    }

    drawHeadFeatures(point, angle, radius, fish) {
        this.ctx.save();
        this.ctx.translate(point.x, point.y);
        this.ctx.rotate(angle);

        this.ctx.fillStyle = '#0d0d0d';
        this.ctx.beginPath();
        this.ctx.arc(radius * 0.34, -radius * 0.12, Math.max(1.4, radius * 0.08), 0, Math.PI * 2);
        this.ctx.fill();

        this.ctx.fillStyle = fish.body;
        this.ctx.beginPath();
        this.ctx.arc(-radius * 0.18, 0, radius * 0.12, 0, Math.PI * 2);
        this.ctx.fill();

        this.ctx.fillStyle = fish.accent;
        this.ctx.font = `${Math.max(10, radius * 1.15)}px monospace`;
        this.ctx.textAlign = 'center';
        this.ctx.textBaseline = 'middle';
        this.ctx.fillText(':', radius * 0.05, -radius * 0.04);

        this.ctx.restore();
    }

    drawFins(point, angle, radius, fish, progress) {
        const finPhase = Math.sin(this.time * 0.012 + progress * 10) * 0.55;

        this.ctx.save();
        this.ctx.translate(point.x, point.y);
        this.ctx.rotate(angle);

        this.ctx.save();
        this.ctx.translate(-radius * 0.95, -radius * 0.15);
        this.ctx.rotate(-0.9 + finPhase * 0.3);
        this.ctx.fillStyle = fish.accent;
        this.ctx.beginPath();
        this.ctx.ellipse(0, 0, radius * 0.55, radius * 0.16, 0.15, 0, Math.PI * 2);
        this.ctx.fill();
        this.ctx.restore();

        this.ctx.save();
        this.ctx.translate(-radius * 0.95, radius * 0.15);
        this.ctx.rotate(0.9 - finPhase * 0.3);
        this.ctx.scale(1, -1);
        this.ctx.fillStyle = fish.accent;
        this.ctx.beginPath();
        this.ctx.ellipse(0, 0, radius * 0.55, radius * 0.16, 0.15, 0, Math.PI * 2);
        this.ctx.fill();
        this.ctx.restore();

        this.ctx.restore();
    }

    drawSegmentedFish(fish) {
        const coilBase = Math.min(this.canvas.width, this.canvas.height) * 0.016;

        for (let index = this.coilCount - 1; index >= 0; index -= 1) {
            const progress = index / (this.coilCount - 1);
            const point = this.getPathPoint(fish, progress * 0.11);
            const nextPoint = this.getPathPoint(fish, Math.min(0.11, progress * 0.11 + 0.01));
            const angle = Math.atan2(nextPoint.y - point.y, nextPoint.x - point.x);
            const radius = coilBase * this.segmentScales[index];
            const wiggle = Math.sin(this.time * 0.01 + progress * 12 + fish.phase * Math.PI * 2) * 0.1;

            this.ctx.save();
            this.ctx.translate(point.x, point.y);
            this.ctx.rotate(angle + wiggle);
            if (fish.mirrored) {
                this.ctx.scale(-1, 1);
            }

            const bodyGradient = this.ctx.createRadialGradient(-radius * 0.25, -radius * 0.2, radius * 0.15, 0, 0, radius);
            bodyGradient.addColorStop(0, fish.accent);
            bodyGradient.addColorStop(0.45, fish.body);
            bodyGradient.addColorStop(1, 'rgba(20, 20, 20, 0.18)');
            this.ctx.fillStyle = bodyGradient;
            this.ctx.shadowColor = fish.shadow;
            this.ctx.shadowBlur = radius * 0.35;
            this.ctx.beginPath();
            this.ctx.ellipse(0, 0, radius, radius * 0.72, 0, 0, Math.PI * 2);
            this.ctx.fill();
            this.ctx.restore();

            if (index === this.coilCount - 1) {
                this.drawTail(point, angle + wiggle, radius, fish);
            }

            if (index === 0) {
                this.drawHeadFeatures(point, angle + wiggle, radius, fish);
            }

            if (index === 3) {
                this.drawFins(point, angle + wiggle, radius, fish, progress);
            }
        }
    }

    drawWater() {
        const gradient = this.ctx.createLinearGradient(0, 0, 0, this.canvas.height);
        gradient.addColorStop(0, '#97d9f5');
        gradient.addColorStop(1, '#2a80a8');
        this.ctx.fillStyle = gradient;
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

        for (let i = 0; i < 4; i += 1) {
            const y = this.canvas.height * (0.16 + i * 0.18);
            this.ctx.strokeStyle = `rgba(255,255,255,${0.08 - i * 0.012})`;
            this.ctx.lineWidth = 10 - i * 1.5;
            this.ctx.beginPath();
            for (let x = 0; x <= this.canvas.width; x += 18) {
                const wave = Math.sin((x / this.canvas.width) * Math.PI * 4 + this.time * 0.004 * (1.4 + i * 0.2)) * (8 + i * 2 + this.windInfluence * 2);
                if (x === 0) {
                    this.ctx.moveTo(x, y + wave);
                } else {
                    this.ctx.lineTo(x, y + wave);
                }
            }
            this.ctx.stroke();
        }
    }

    draw() {
        this.time += 16;
        this.drawWater();
        this.fishes.forEach((fish) => this.drawSegmentedFish(fish));
    }

    onDataUpdate() {
        if (this.data.weather) {
            const wind = Number(this.data.weather.windSpeed || 0);
            this.windInfluence = Math.max(0, Math.min(1.6, wind / 14));
        }
    }
}

if (typeof window !== 'undefined') {
    window.KoiFishAnimation = KoiFishAnimation;
}
