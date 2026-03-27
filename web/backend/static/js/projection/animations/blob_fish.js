// Blob Fish Animation - internal canvas port inspired by soft CSS blob fish studies
class BlobFishAnimation extends BaseAnimation {
    setup() {
        this.time = 0;
        this.blobs = Array.from({ length: 3 }, (_, index) => ({
            x: this.canvas.width * (0.2 + index * 0.28),
            y: this.canvas.height * (0.34 + (index % 2) * 0.2),
            scale: 0.85 + index * 0.18,
            hue: [342, 18, 202][index % 3],
            drift: Math.random() * Math.PI * 2,
            speed: 0.0007 + index * 0.00012,
        }));
        this.brightnessGain = 1;
    }

    drawBlob(blob, index) {
        const t = this.time * blob.speed + blob.drift;
        const x = blob.x + Math.sin(t * 1.9) * this.canvas.width * 0.12;
        const y = blob.y + Math.cos(t * 1.4) * this.canvas.height * 0.1;
        const scale = blob.scale * (0.92 + Math.sin(t * 2.7) * 0.06);
        const width = this.canvas.width * 0.22 * scale;
        const height = this.canvas.height * 0.19 * scale;

        this.ctx.save();
        this.ctx.translate(x, y);
        this.ctx.rotate(Math.sin(t * 1.7) * 0.18);

        const bodyGradient = this.ctx.createLinearGradient(-width * 0.5, -height * 0.4, width * 0.5, height * 0.5);
        bodyGradient.addColorStop(0, `hsla(${blob.hue}, 72%, ${78 * this.brightnessGain}%, 0.96)`);
        bodyGradient.addColorStop(0.5, `hsla(${blob.hue}, 56%, ${67 * this.brightnessGain}%, 0.95)`);
        bodyGradient.addColorStop(1, `hsla(${blob.hue + 18}, 38%, ${43 * this.brightnessGain}%, 0.95)`);
        this.ctx.fillStyle = bodyGradient;

        this.ctx.beginPath();
        this.ctx.moveTo(-width * 0.38, 0);
        this.ctx.bezierCurveTo(-width * 0.5, -height * 0.45, width * 0.24, -height * 0.52, width * 0.46, -height * 0.08);
        this.ctx.bezierCurveTo(width * 0.58, height * 0.18, width * 0.18, height * 0.54, -width * 0.22, height * 0.45);
        this.ctx.bezierCurveTo(-width * 0.5, height * 0.34, -width * 0.52, height * 0.12, -width * 0.38, 0);
        this.ctx.fill();

        this.ctx.fillStyle = 'rgba(255,255,255,0.2)';
        this.ctx.beginPath();
        this.ctx.ellipse(width * 0.05, -height * 0.18, width * 0.2, height * 0.1, -0.2, 0, Math.PI * 2);
        this.ctx.fill();

        this.ctx.fillStyle = '#17151e';
        this.ctx.beginPath();
        this.ctx.arc(width * 0.15, -height * 0.05, Math.max(3, width * 0.028), 0, Math.PI * 2);
        this.ctx.arc(width * 0.28, -height * 0.01, Math.max(3, width * 0.028), 0, Math.PI * 2);
        this.ctx.fill();

        this.ctx.strokeStyle = 'rgba(71, 34, 50, 0.55)';
        this.ctx.lineWidth = Math.max(2, width * 0.016);
        this.ctx.beginPath();
        this.ctx.moveTo(width * 0.08, height * 0.14);
        this.ctx.quadraticCurveTo(width * 0.22, height * 0.22, width * 0.34, height * 0.12);
        this.ctx.stroke();

        const finSwing = Math.sin(this.time * 0.01 + index * 1.7) * 0.45;
        this.ctx.save();
        this.ctx.translate(-width * 0.26, height * 0.02);
        this.ctx.rotate(-0.6 + finSwing * 0.5);
        this.ctx.fillStyle = `hsla(${blob.hue + 4}, 48%, 62%, 0.85)`;
        this.ctx.beginPath();
        this.ctx.ellipse(0, 0, width * 0.09, height * 0.2, 0.3, 0, Math.PI * 2);
        this.ctx.fill();
        this.ctx.restore();

        this.ctx.save();
        this.ctx.translate(width * 0.42, 0);
        this.ctx.rotate(Math.sin(this.time * 0.012 + blob.drift) * 0.5);
        this.ctx.fillStyle = `hsla(${blob.hue - 8}, 42%, 58%, 0.85)`;
        this.ctx.beginPath();
        this.ctx.moveTo(0, 0);
        this.ctx.quadraticCurveTo(width * 0.16, -height * 0.18, width * 0.24, 0);
        this.ctx.quadraticCurveTo(width * 0.16, height * 0.18, 0, 0);
        this.ctx.fill();
        this.ctx.restore();

        this.ctx.restore();
    }

    draw() {
        this.time += 16;

        const bg = this.ctx.createLinearGradient(0, 0, 0, this.canvas.height);
        bg.addColorStop(0, '#0b1832');
        bg.addColorStop(0.5, '#103d67');
        bg.addColorStop(1, '#0a2744');
        this.ctx.fillStyle = bg;
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

        for (let i = 0; i < 18; i++) {
            const alpha = 0.03 + (i % 3) * 0.01;
            this.ctx.fillStyle = `rgba(255,255,255,${alpha})`;
            const px = ((i * 79) % (this.canvas.width + 120)) - 60;
            const py = (this.canvas.height * 0.12) + ((i * 53) % Math.max(120, this.canvas.height * 0.72));
            const wobble = Math.sin(this.time * 0.0018 + i) * 12;
            this.ctx.beginPath();
            this.ctx.arc(px + wobble, py, 2 + (i % 4), 0, Math.PI * 2);
            this.ctx.fill();
        }

        this.blobs.forEach((blob, index) => this.drawBlob(blob, index));
    }

    onDataUpdate() {
        if (this.data.weather) {
            const humidity = Number(this.data.weather.humidity || 50);
            this.brightnessGain = 0.88 + Math.min(0.3, humidity / 300);
        }
    }
}
