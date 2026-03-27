// Fish Pond Animation - internal canvas port inspired by layered CSS fish pond scenes
class FishPondAnimation extends BaseAnimation {
    setup() {
        this.time = 0;
        this.fish = Array.from({ length: 9 }, (_, index) => ({
            progress: index / 9,
            lane: index % 4,
            color: ['#ff8f00', '#ef6c00', '#8bc34a', '#7e57c2', '#d81b60'][index % 5],
            size: 0.55 + (index % 3) * 0.15,
            speed: 0.00003 + index * 0.0000025,
            phase: Math.random() * Math.PI * 2,
        }));
        this.bubbleRate = 1;
    }

    drawBackground() {
        const water = this.ctx.createLinearGradient(0, 0, 0, this.canvas.height);
        water.addColorStop(0, '#0d3760');
        water.addColorStop(0.55, '#0b5f84');
        water.addColorStop(1, '#09324a');
        this.ctx.fillStyle = water;
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

        for (let i = 0; i < 4; i++) {
            const y = this.canvas.height * (0.14 + i * 0.17);
            this.ctx.strokeStyle = `rgba(255,255,255,${0.035 + i * 0.008})`;
            this.ctx.lineWidth = 7 - i;
            this.ctx.beginPath();
            for (let x = 0; x <= this.canvas.width; x += 14) {
                const wave = Math.sin(x * 0.02 + this.time * 0.0018 + i) * (6 + i * 2);
                if (x === 0) this.ctx.moveTo(x, y + wave);
                else this.ctx.lineTo(x, y + wave);
            }
            this.ctx.stroke();
        }

        const floorY = this.canvas.height * 0.84;
        const floorGradient = this.ctx.createLinearGradient(0, floorY, 0, this.canvas.height);
        floorGradient.addColorStop(0, '#8d6f49');
        floorGradient.addColorStop(1, '#58442d');
        this.ctx.fillStyle = floorGradient;
        this.ctx.fillRect(0, floorY, this.canvas.width, this.canvas.height - floorY);

        this.ctx.fillStyle = 'rgba(42, 84, 52, 0.85)';
        for (let i = 0; i < 7; i++) {
            const baseX = this.canvas.width * (0.08 + i * 0.13);
            const height = this.canvas.height * (0.12 + (i % 3) * 0.08);
            this.ctx.beginPath();
            this.ctx.moveTo(baseX, floorY);
            this.ctx.quadraticCurveTo(
                baseX + Math.sin(this.time * 0.0014 + i) * 18,
                floorY - height * 0.5,
                baseX + Math.cos(this.time * 0.0012 + i) * 12,
                floorY - height
            );
            this.ctx.lineWidth = 8 - (i % 3) * 2;
            this.ctx.strokeStyle = `rgba(${38 + i * 10}, ${110 + i * 8}, ${52 + i * 3}, 0.75)`;
            this.ctx.stroke();
        }
    }

    drawFish(fish, index) {
        const t = (this.time * fish.speed + fish.progress) % 1;
        const x = -90 + t * (this.canvas.width + 180);
        const laneY = this.canvas.height * (0.22 + fish.lane * 0.15);
        const y = laneY + Math.sin(this.time * 0.002 + fish.phase + index) * 18;
        const scale = fish.size * (1 + Math.sin(this.time * 0.006 + index) * 0.04);
        const bodyLength = 70 * scale;
        const bodyHeight = 30 * scale;
        const direction = Math.sin(this.time * fish.speed + fish.phase) > -0.98 ? 1 : 1;

        this.ctx.save();
        this.ctx.translate(x, y);
        this.ctx.scale(direction, 1);
        this.ctx.rotate(Math.sin(this.time * 0.004 + fish.phase) * 0.08);

        const bodyGradient = this.ctx.createLinearGradient(-bodyLength * 0.5, 0, bodyLength * 0.5, 0);
        bodyGradient.addColorStop(0, 'rgba(255,255,255,0.24)');
        bodyGradient.addColorStop(0.2, fish.color);
        bodyGradient.addColorStop(1, 'rgba(55, 24, 10, 0.72)');
        this.ctx.fillStyle = bodyGradient;
        this.ctx.beginPath();
        this.ctx.ellipse(0, 0, bodyLength * 0.5, bodyHeight * 0.72, 0, 0, Math.PI * 2);
        this.ctx.fill();

        this.ctx.fillStyle = 'rgba(255,255,255,0.16)';
        this.ctx.beginPath();
        this.ctx.ellipse(bodyLength * 0.05, -bodyHeight * 0.12, bodyLength * 0.22, bodyHeight * 0.16, 0, 0, Math.PI * 2);
        this.ctx.fill();

        this.ctx.save();
        this.ctx.translate(-bodyLength * 0.48, 0);
        this.ctx.rotate(Math.sin(this.time * 0.014 + fish.phase) * 0.55);
        this.ctx.fillStyle = fish.color;
        this.ctx.beginPath();
        this.ctx.moveTo(0, 0);
        this.ctx.lineTo(-bodyLength * 0.34, -bodyHeight * 0.46);
        this.ctx.lineTo(-bodyLength * 0.26, 0);
        this.ctx.lineTo(-bodyLength * 0.34, bodyHeight * 0.46);
        this.ctx.closePath();
        this.ctx.fill();
        this.ctx.restore();

        this.ctx.fillStyle = '#13110f';
        this.ctx.beginPath();
        this.ctx.arc(bodyLength * 0.24, -bodyHeight * 0.08, Math.max(2, 2.5 * scale), 0, Math.PI * 2);
        this.ctx.fill();

        this.ctx.restore();
    }

    drawBubbles() {
        const bubbleColumns = 3 + Math.round(this.bubbleRate * 2);
        for (let col = 0; col < bubbleColumns; col++) {
            const baseX = this.canvas.width * (0.12 + col * (0.72 / Math.max(1, bubbleColumns - 1)));
            for (let i = 0; i < 6; i++) {
                const offset = (this.time * (0.03 + col * 0.004) + i * 68) % (this.canvas.height + 80);
                const y = this.canvas.height - offset;
                const wobble = Math.sin(this.time * 0.002 + i + col) * 10;
                this.ctx.strokeStyle = 'rgba(255,255,255,0.35)';
                this.ctx.lineWidth = 1.4;
                this.ctx.beginPath();
                this.ctx.arc(baseX + wobble, y, 4 + (i % 3), 0, Math.PI * 2);
                this.ctx.stroke();
            }
        }
    }

    draw() {
        this.time += 16;
        this.drawBackground();
        this.drawBubbles();
        this.fish.forEach((fish, index) => this.drawFish(fish, index));
    }

    onDataUpdate() {
        if (this.data.transit) {
            const count = Number(this.data.transit.count || (this.data.transit.activeRoutes || []).length || 0);
            this.bubbleRate = 0.8 + Math.min(1.6, count * 0.12);
            this.fish.forEach((fish, index) => {
                fish.speed = 0.000028 + index * 0.000002 + count * 0.0000009;
            });
        }
    }
}

if (typeof window !== 'undefined') {
    window.FishPondAnimation = FishPondAnimation;
}
