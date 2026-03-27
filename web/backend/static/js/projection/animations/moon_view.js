class MoonViewAnimation extends BaseAnimation {
    setup() {
        this.time = 0;
        this.glCanvas = document.createElement('canvas');
        this.glCanvas.width = this.canvas.width;
        this.glCanvas.height = this.canvas.height;

        this.gl = null;
        this.program = null;
        this.vertexBuffer = null;
        this.uniforms = {};

        this.initWebGL();
    }

    initWebGL() {
        this.gl =
            this.glCanvas.getContext('webgl2', { alpha: false, antialias: true }) ||
            this.glCanvas.getContext('webgl2');

        if (!this.gl) {
            console.error('MoonViewAnimation requires WebGL2');
            return;
        }

        const vertexSource = `#version 300 es
            in vec2 a_position;
            void main() {
                gl_Position = vec4(a_position, 0.0, 1.0);
            }
        `;

        const fragmentSource = `#version 300 es
            precision highp float;
            out vec4 O;
            uniform float time;
            uniform vec2 resolution;
            #define FC gl_FragCoord.xy
            #define R resolution
            #define T (time+360.)
            #define N normalize
            #define S smoothstep
            #define SE(v,s,k) S(s+k/MN,s-k/MN,v)
            #define MN min(R.x,R.y)
            #define hue(a) (.24+.4*fcos(6.3*(a)+vec3(0,83,21)))
            #define fcos(a) (cos(a)*S(6.3,.0,fwidth(a)))
            #define rot(a) mat2(cos((a)-vec4(0,11,33,0)))
            #define MAXD 100.
            #define ALPHA -.42
            float rnd(vec2 p) {
                p=fract(p*vec2(12.9898,78.233));
                p+=dot(p,p+34.56);
                return fract(p.x*p.y);
            }
            float noise(vec2 p) {
                vec2 i=floor(p), f=fract(p), u=f*f*(3.-2.*f), k=vec2(1,0);
                float a=rnd(i), b=rnd(i+k), c=rnd(i+k.yx), d=rnd(i+1.);
                return mix(mix(a,b,u.x),mix(c,d,u.x),u.y);
            }
            float fbm(vec2 p) {
                float t=.0, a=1., h=.0;
                for (float i=.0; i<5.; i++) {
                    t+=a*noise(p);
                    p*=2.;
                    a*=.5;
                    h+=a;
                }
                return t/h;
            }
            vec3 sky(vec2 p, bool anim) {
                p*=rot(ALPHA);
                p.x-=.17-(anim?2e-4*T:.0);
                p*=500.;
                vec2 id=floor(p), gv=fract(p)-.5;
                float n=rnd(id), d=length(gv);
                if (n<.95) return vec3(0);
                return vec3(S(3e-2*n,1e-3*n,d*d));
            }
            float glow=.0;
            float map(vec3 p) {
                float obj=length(p+vec3(0,-2,1))-1.;
                glow+=.0125/(.025+obj*obj*obj*80.);
                if (p.y>.0) return obj;
                vec2 st=vec2(p.x,p.z-T*.05);
                float f1=fbm(st*.5), n1=fbm(st+f1), n2=f1, n=abs(n1-n2);
                n=S(-.2,2.,(n-.1));
                n*=n;
                return p.y+(1.-mix(.0,.1*n,S(30.,.0,length(p.xz))));
            }
            vec3 norm(vec3 p) {
                float h=1e-3; vec2 k=vec2(-1,1);
                return N(
                    k.xyy*map(p+k.xyy*h)+
                    k.yxy*map(p+k.yxy*h)+
                    k.yyx*map(p+k.yyx*h)+
                    k.xxx*map(p+k.xxx*h)
                );
            }
            float march(inout vec3 p, vec3 rd) {
                float dd=.0;
                for (float i=.0; i<400.; i++) {
                    float d=map(p);
                    if (abs(d)<1e-3 || dd>MAXD) break;
                    p+=rd*d;
                    dd+=d;
                }
                return dd;
            }
            vec3 renderScene(inout vec3 p, vec3 rd) {
                vec3 col=vec3(0);
                float d=march(p,rd);
                if (d<MAXD) {
                    vec3 n=norm(p), lp=vec3(23,5,20), l=N(lp-p);
                    float dif=clamp(dot(l,n),.0,1.);
                    col+=dif;
                    if (p.y>.9) {
                        vec3 q=(p);
                        q.xy*=rot(.42);
                        vec2 sn=vec2(atan(q.x+2.7,q.z)*6./6.28318,q.y);
                        col+=hue(vec3(0,1.25,.2)*fbm(sn+noise(6.*sn+vec2(T*.04,0))));
                        col+=pow(clamp(dot(reflect(rd,n),l),.0,1.),2.);
                        col=.08+tanh(col)*pow(clamp(1.-dot(rd,n),.0,1.),5.);
                        col*=col;
                    } else {
                        float ldst = max(length(lp-p), 1e-3), fade=1./(1.+ldst*.125+ldst*ldst*.05);
                        col*=hue(.1);
                        col+=d*hue(.5+clamp(length(p.xz*.01),.0,.2))*fade;
                    }
                    col=mix(vec3(1),col,exp(-125e-7*d*d*d));
                } else {
                    vec2 sn=.5+vec2(atan(rd.x,rd.z),atan(length(rd.xz),rd.y))/6.28318;
                    col=vec3(sky(sn,true)+sky(sn*2.,true)+sky(sn*4.,false)+sky(sn*8.,false));
                }
                col=mix(col,mix(vec3(1),vec3(.3,.6,.9),S(-.2,.0,p.y+.86)),S(.08,.03,abs(p.y+.92)));
                col=mix(col,vec3(.1,.2,.3),S(.2,.0,abs(p.y+.799)));
                return col;
            }
            float rnd1(float a) {
                vec2 p=fract(a*vec2(12.9898,78.233));
                p+=dot(p,p+34.56);
                return fract(p.x*p.y);
            }
            float curve(float t, float e) {
                t/=e;
                return mix(
                    rnd1(floor(t)),
                    rnd1(floor(t)+1.),
                    pow(S(.0,1.,fract(t)),10.)
                );
            }
            float logo(vec2 p, float k) {
                p*=k;
                p*=rot(-1.57+3.1415*curve(T,.4));
                vec2 q=p;
                q.x=abs(abs(q.x)-.2);
                q.y+=q.x-.2;
                float d=.0;
                d+=SE(length(q),.1,k);
                d=max(d,SE(abs(length(p)-.225)-.025,.0,k));
                return d;
            }
            float placeLogo() {
                vec2 p=FC/R;
                p*=vec2(R.x/R.y,1.);
                p-=vec2(R.x/R.y,0.);
                p+=vec2(.075,-.05);
                return logo(p,24.);
            }
            void main() {
                vec2 uv=(FC-.5*R)/MN;
                uv*=rot(ALPHA);
                vec3 col=vec3(0), p=vec3(0,-.2,-10.), rd=N(vec3(uv,1.7));
                col+=renderScene(p,rd);
                col=pow(col,vec3(.4545));
                col=tanh(col*col);
                col+=.15*pow(glow,.15)*vec3(.8,.95,1.);
                col=clamp(col+.1*placeLogo(),.08,1.);
                O=vec4(col,1.);
            }
        `;

        const vertexShader = this.createShader(vertexSource, this.gl.VERTEX_SHADER);
        const fragmentShader = this.createShader(fragmentSource, this.gl.FRAGMENT_SHADER);
        if (!vertexShader || !fragmentShader) {
            return;
        }

        this.program = this.gl.createProgram();
        this.gl.attachShader(this.program, vertexShader);
        this.gl.attachShader(this.program, fragmentShader);
        this.gl.linkProgram(this.program);

        if (!this.gl.getProgramParameter(this.program, this.gl.LINK_STATUS)) {
            console.error('MoonViewAnimation link error:', this.gl.getProgramInfoLog(this.program));
            return;
        }

        this.vertexBuffer = this.gl.createBuffer();
        this.gl.bindBuffer(this.gl.ARRAY_BUFFER, this.vertexBuffer);
        this.gl.bufferData(
            this.gl.ARRAY_BUFFER,
            new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]),
            this.gl.STATIC_DRAW
        );

        this.gl.useProgram(this.program);
        const positionLocation = this.gl.getAttribLocation(this.program, 'a_position');
        this.gl.enableVertexAttribArray(positionLocation);
        this.gl.vertexAttribPointer(positionLocation, 2, this.gl.FLOAT, false, 0, 0);

        this.uniforms = {
            time: this.gl.getUniformLocation(this.program, 'time'),
            resolution: this.gl.getUniformLocation(this.program, 'resolution'),
        };
    }

    createShader(source, type) {
        const shader = this.gl.createShader(type);
        this.gl.shaderSource(shader, source);
        this.gl.compileShader(shader);

        if (!this.gl.getShaderParameter(shader, this.gl.COMPILE_STATUS)) {
            console.error('MoonViewAnimation shader error:', this.gl.getShaderInfoLog(shader));
            this.gl.deleteShader(shader);
            return null;
        }

        return shader;
    }

    draw() {
        if (!this.gl || !this.program) {
            this.ctx.fillStyle = '#000';
            this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
            return;
        }

        if (this.glCanvas.width !== this.canvas.width || this.glCanvas.height !== this.canvas.height) {
            this.glCanvas.width = this.canvas.width;
            this.glCanvas.height = this.canvas.height;
        }

        this.time += 16;

        this.gl.viewport(0, 0, this.glCanvas.width, this.glCanvas.height);
        this.gl.clearColor(0, 0, 0, 1);
        this.gl.clear(this.gl.COLOR_BUFFER_BIT);
        this.gl.useProgram(this.program);
        this.gl.uniform1f(this.uniforms.time, this.time * 0.001);
        this.gl.uniform2f(this.uniforms.resolution, this.glCanvas.width, this.glCanvas.height);
        this.gl.drawArrays(this.gl.TRIANGLE_STRIP, 0, 4);

        this.ctx.drawImage(this.glCanvas, 0, 0, this.canvas.width, this.canvas.height);
    }
}

window.MoonViewAnimation = MoonViewAnimation;
