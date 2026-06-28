import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import './ProjectionMapping.css';

function ProjectionMapping() {
    const [originalImage, setOriginalImage] = useState(null);
    const [layers, setLayers] = useState([]);
    const [currentLayerIndex, setCurrentLayerIndex] = useState(-1);
    const [currentTool, setCurrentTool] = useState('floodFill');
    const [edgeSensitivity, setEdgeSensitivity] = useState(50);
    const [tolerance, setTolerance] = useState(20);
    const [brushSize, setBrushSize] = useState(10);
    const [isDrawing, setIsDrawing] = useState(false);
    const [status, setStatus] = useState('');
    const [bezierPoints, setBezierPoints] = useState([]);
    const [cursorPosition, setCursorPosition] = useState({ x: 0, y: 0, canvasX: 0, canvasY: 0, visible: false, activeCanvas: null });
    const [autoLayerCount, setAutoLayerCount] = useState(5);
    const [isProcessingAutoLayers, setIsProcessingAutoLayers] = useState(false);
    const [processingProgress, setProcessingProgress] = useState(0);
    const [processingStep, setProcessingStep] = useState('');
    const [baseTransform, setBaseTransform] = useState({ 
        mode: 'basic', // 'basic' or 'corners'
        x: 0, y: 0, scale: 1, rotation: 0,
        corners: {
            topLeft: { x: 0, y: 0 },
            topRight: { x: 1000, y: 0 },
            bottomLeft: { x: 0, y: 600 },
            bottomRight: { x: 1000, y: 600 }
        }
    });
    const [edgeProcessing, setEdgeProcessing] = useState(false);
    const [brushMode, setBrushMode] = useState('solid'); // 'solid' or 'spray'
    const [brushShape, setBrushShape] = useState('circle'); // 'circle' or 'square'
    const [magicWandMode] = useState('radius'); // 'radius' or 'point'
    
    // Selection tool states
    const [selection, setSelection] = useState(null); // { x, y, width, height, data: ImageData }
    const [selectionStart, setSelectionStart] = useState(null);
    const [isSelecting, setIsSelecting] = useState(false);
    const [clipboard, setClipboard] = useState(null); // { width, height, data: ImageData }
    const [selectedLayers, setSelectedLayers] = useState(new Set()); // For multi-layer selection
    const [isFullscreenMode, setIsFullscreenMode] = useState(false); // For fullscreen editing mode
    const [canvasZoom, setCanvasZoom] = useState(1); // Zoom level for canvas (0.1 to 5)
    
    const originalCanvasRef = useRef(null);
    const edgeCanvasRef = useRef(null);
    const combinedCanvasRef = useRef(null);
    const currentCanvasRef = useRef(null);
    
    const layerHistoryRef = useRef(new Map());
    const projectionWindowsRef = useRef(new Map());
    const cachedImageDataRef = useRef(null);
    const cachedEdgeDataRef = useRef(null);
    const precomputedEdgesRef = useRef(null); // Store all edge magnitudes
    const edgeUpdateTimerRef = useRef(null);
    const layersRef = useRef(layers); // Keep current layers state for event handlers
    
    // Brush optimization refs
    const brushCanvasRef = useRef(null);
    const brushCtxRef = useRef(null);
    const lastBrushPosRef = useRef(null);
    const dirtyRectRef = useRef(null);
    const brushUpdateTimerRef = useRef(null);
    
    // Cache canvas contexts
    const contextsRef = useRef({
        original: null,
        edge: null,
        combined: null,
        current: null
    });
    
    // Canvas work ref for direct manipulation
    const canvasWorkRef = useRef({
        isProcessing: false,
        pendingUpdates: [],
        maskCache: new Map(), // Cache mask data for direct manipulation
        updateTimer: null,
        contentScale: 1, // Scale factor for fullscreen content
        contentOffset: { x: 0, y: 0 } // Offset for centered content
    });
    
    // Cache for preview bounds to prevent unnecessary recalculations
    const boundsCache = useRef({
        lastLayersHash: '',
        lastBaseTransform: null,
        currentBounds: null,
        combinedBounds: null
    });
    
    // Canvas pool for performance optimization
    const canvasPool = useRef([]);
    const getPooledCanvas = useCallback((width, height) => {
        // Find an available canvas with matching dimensions
        let canvas = canvasPool.current.find(c => 
            !c.inUse && c.width === width && c.height === height
        );
        
        if (!canvas) {
            // Create new canvas if none available
            canvas = document.createElement('canvas');
            canvas.width = width;
            canvas.height = height;
            canvasPool.current.push(canvas);
        }
        
        canvas.inUse = true;
        return canvas;
    }, []);
    
    const releasePooledCanvas = useCallback((canvas) => {
        if (canvas && canvas.inUse) {
            canvas.inUse = false;
            // Clear the canvas for reuse
            const ctx = canvas.getContext('2d');
            ctx.clearRect(0, 0, canvas.width, canvas.height);
        }
    }, []);
    
    // Simple debounce implementation
    const debounce = useCallback((func, wait) => {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }, []);
    
    // Helper function to get cached context
    const getContext = useCallback((canvasRef, contextKey) => {
        if (!contextsRef.current[contextKey] && canvasRef.current) {
            contextsRef.current[contextKey] = canvasRef.current.getContext('2d', { willReadFrequently: true });
        }
        return contextsRef.current[contextKey];
    }, []);
    
    // Get the appropriate cursor style based on the current tool
    const getCursorStyle = useCallback(() => {
        switch (currentTool) {
            case 'brush':
            case 'eraser':
                return 'none'; // Hide cursor for brush/eraser (we show custom preview)
            case 'floodFill':
                return 'url("data:image/svg+xml;utf8,<svg xmlns=\'http://www.w3.org/2000/svg\' width=\'32\' height=\'32\' viewBox=\'0 0 32 32\'><path d=\'M16 2 L12 10 L20 10 Z\' fill=\'white\' stroke=\'black\'/><rect x=\'14\' y=\'10\' width=\'4\' height=\'20\' fill=\'white\' stroke=\'black\'/></svg>") 16 2, auto';
            case 'magicWand':
                return 'url("data:image/svg+xml;utf8,<svg xmlns=\'http://www.w3.org/2000/svg\' width=\'32\' height=\'32\' viewBox=\'0 0 32 32\'><circle cx=\'16\' cy=\'16\' r=\'8\' fill=\'none\' stroke=\'white\' stroke-width=\'2\'/><circle cx=\'16\' cy=\'16\' r=\'8\' fill=\'none\' stroke=\'black\' stroke-width=\'1\'/><line x1=\'16\' y1=\'4\' x2=\'16\' y2=\'8\' stroke=\'white\' stroke-width=\'2\'/><line x1=\'16\' y1=\'24\' x2=\'16\' y2=\'28\' stroke=\'white\' stroke-width=\'2\'/><line x1=\'4\' y1=\'16\' x2=\'8\' y2=\'16\' stroke=\'white\' stroke-width=\'2\'/><line x1=\'24\' y1=\'16\' x2=\'28\' y2=\'16\' stroke=\'white\' stroke-width=\'2\'/></svg>") 16 16, auto';
            case 'bezier':
                return 'url("data:image/svg+xml;utf8,<svg xmlns=\'http://www.w3.org/2000/svg\' width=\'32\' height=\'32\' viewBox=\'0 0 32 32\'><circle cx=\'16\' cy=\'16\' r=\'4\' fill=\'white\' stroke=\'black\'/><path d=\'M8 24 Q 16 8, 24 24\' fill=\'none\' stroke=\'white\' stroke-width=\'2\'/><path d=\'M8 24 Q 16 8, 24 24\' fill=\'none\' stroke=\'black\' stroke-width=\'1\'/></svg>") 16 16, auto';
            case 'despeckle':
                return 'url("data:image/svg+xml;utf8,<svg xmlns=\'http://www.w3.org/2000/svg\' width=\'32\' height=\'32\' viewBox=\'0 0 32 32\'><circle cx=\'8\' cy=\'8\' r=\'2\' fill=\'white\' stroke=\'black\'/><circle cx=\'24\' cy=\'8\' r=\'2\' fill=\'white\' stroke=\'black\'/><circle cx=\'16\' cy=\'16\' r=\'2\' fill=\'white\' stroke=\'black\'/><circle cx=\'8\' cy=\'24\' r=\'2\' fill=\'white\' stroke=\'black\'/><circle cx=\'24\' cy=\'24\' r=\'2\' fill=\'white\' stroke=\'black\'/><path d=\'M16 10 L16 14 M16 18 L16 22 M10 16 L14 16 M18 16 L22 16\' stroke=\'white\' stroke-width=\'2\'/></svg>") 16 16, auto';
            default:
                return 'crosshair';
        }
    }, [currentTool]);
    
    // Helper function to calculate perspective transform matrix
    const calculatePerspectiveTransform = useCallback((src, dst) => {
        // This is a simplified version - for production use, consider a library like gl-matrix
        // Calculate the transformation matrix that maps src points to dst points
        
        const A = [];
        const b = [];
        
        for (let i = 0; i < 4; i++) {
            const [sx, sy] = src[i];
            const [dx, dy] = dst[i];
            
            A.push([sx, sy, 1, 0, 0, 0, -dx * sx, -dx * sy]);
            A.push([0, 0, 0, sx, sy, 1, -dy * sx, -dy * sy]);
            
            b.push(dx);
            b.push(dy);
        }
        
        // Solve the linear system Ax = b to get the transformation matrix
        // For simplicity, we'll use a basic matrix solution
        // In production, use a proper matrix library
        
        // For now, return a CSS transform matrix string
        // This is a simplified approach that works for basic perspective
        const matrix3d = `matrix3d(
            ${(dst[1][0] - dst[0][0]) / src[1][0]}, ${(dst[1][1] - dst[0][1]) / src[1][0]}, 0, 0,
            ${(dst[2][0] - dst[0][0]) / src[2][1]}, ${(dst[2][1] - dst[0][1]) / src[2][1]}, 0, 0,
            0, 0, 1, 0,
            ${dst[0][0]}, ${dst[0][1]}, 0, 1
        )`;
        
        return matrix3d;
    }, []);
    
    // Calculate perspective matrix based on corner coordinates
    const calculatePerspectiveMatrix = useCallback((corners, sourceWidth, sourceHeight) => {
        // Source points (original rectangle corners)
        const src = [
            [0, 0],                    // top-left
            [sourceWidth, 0],          // top-right
            [0, sourceHeight],         // bottom-left
            [sourceWidth, sourceHeight] // bottom-right
        ];
        
        // Destination points (user-defined corners)
        const dst = [
            [corners.topLeft.x, corners.topLeft.y],
            [corners.topRight.x, corners.topRight.y],
            [corners.bottomLeft.x, corners.bottomLeft.y],
            [corners.bottomRight.x, corners.bottomRight.y]
        ];
        
        // Calculate perspective transformation matrix
        // This implements the math for mapping a rectangle to an arbitrary quadrilateral
        const matrix = calculatePerspectiveTransform(src, dst);
        
        return matrix;
    }, [calculatePerspectiveTransform]);
    
    // Apply perspective transform to canvas element
    const applyPerspectiveTransform = useCallback((canvasElement, corners, sourceWidth, sourceHeight) => {
        if (!canvasElement || !corners) return;
        
        if (baseTransform.mode === 'corners') {
            const matrix = calculatePerspectiveMatrix(corners, sourceWidth, sourceHeight);
            canvasElement.style.transform = matrix;
            canvasElement.style.transformOrigin = '0 0';
        } else {
            // Clear perspective transform in basic mode
            canvasElement.style.transform = '';
            canvasElement.style.transformOrigin = '';
        }
    }, [baseTransform.mode, calculatePerspectiveMatrix]);
    
    // Transform mouse coordinates to layer space accounting for all transformations
    const transformMouseToLayer = useCallback((mouseX, mouseY, layer) => {
        if (!originalImage) return { x: mouseX, y: mouseY };
        
        // Get canvas center
        const centerX = originalImage.width / 2;
        const centerY = originalImage.height / 2;
        
        // Start with mouse coordinates relative to center
        let x = mouseX - centerX;
        let y = mouseY - centerY;
        
        // Apply inverse base transform first (in reverse order: translate, rotate, scale)
        x -= baseTransform.x;
        y -= baseTransform.y;
        
        // Inverse rotation for base transform
        const baseAngle = -baseTransform.rotation * Math.PI / 180;
        const baseCos = Math.cos(baseAngle);
        const baseSin = Math.sin(baseAngle);
        let tempX = x * baseCos - y * baseSin;
        let tempY = x * baseSin + y * baseCos;
        x = tempX;
        y = tempY;
        
        // Inverse scale for base transform
        x = x / baseTransform.scale;
        y = y / baseTransform.scale;
        
        // Apply inverse layer transform (in reverse order: translate, rotate, scale)
        x -= layer.transform.x;
        y -= layer.transform.y;
        
        // Inverse rotation for layer transform
        const layerAngle = -layer.transform.rotation * Math.PI / 180;
        const layerCos = Math.cos(layerAngle);
        const layerSin = Math.sin(layerAngle);
        tempX = x * layerCos - y * layerSin;
        tempY = x * layerSin + y * layerCos;
        x = tempX;
        y = tempY;
        
        // Inverse scale for layer transform
        x = x / layer.transform.scale;
        y = y / layer.transform.scale;
        
        // Convert back to image coordinates
        return {
            x: Math.floor(x + centerX),
            y: Math.floor(y + centerY)
        };
    }, [originalImage, baseTransform]);
    
    // Batch update system
    const flushPendingUpdates = useCallback(() => {
        if (canvasWorkRef.current.pendingUpdates.length === 0) return;
        
        const updates = [...canvasWorkRef.current.pendingUpdates];
        canvasWorkRef.current.pendingUpdates = [];
        
        // Apply all updates at once
        setLayers(currentLayers => {
            const newLayers = [...currentLayers];
            updates.forEach(update => {
                const layerIndex = newLayers.findIndex(l => l.id === update.layerId);
                if (layerIndex >= 0) {
                    newLayers[layerIndex] = {
                        ...newLayers[layerIndex],
                        ...update.changes
                    };
                }
            });
            return newLayers;
        });
    }, []);
    
    useEffect(() => {
        if (status) {
            const timer = setTimeout(() => setStatus(''), 3000);
            return () => clearTimeout(timer);
        }
    }, [status]);

    const handleImageUpload = (e) => {
        const file = e.target.files[0];
        if (!file) return;
        
        const reader = new FileReader();
        reader.onload = (event) => {
            const img = new Image();
            img.onload = () => {
                setOriginalImage(img);
                initializeCanvases(img);
                updateEdgeDetection(img);
                setStatus('Image loaded successfully');
            };
            img.src = event.target.result;
        };
        reader.readAsDataURL(file);
    };
    
    const handleLayerImport = async (e) => {
        const files = Array.from(e.target.files);
        if (!files.length) return;
        
        if (!originalImage) {
            setStatus('Please upload a base image first');
            return;
        }
        
        setStatus(`Processing ${files.length} files...`);
        
        let successCount = 0;
        let firstLayerIndex = layers.length;
        
        // Process files one at a time to avoid memory issues
        for (let fileIndex = 0; fileIndex < files.length; fileIndex++) {
            const file = files[fileIndex];
            
            // Update status for each file
            setStatus(`Processing file ${fileIndex + 1} of ${files.length}: ${file.name}`);
            
            try {
                const layerData = await new Promise((resolve, reject) => {
                    const reader = new FileReader();
                    reader.onload = (event) => {
                        const img = new Image();
                        img.onload = () => {
                            // Create a canvas to read the image data
                            const canvas = document.createElement('canvas');
                            canvas.width = originalImage.width;
                            canvas.height = originalImage.height;
                            const ctx = canvas.getContext('2d', { willReadFrequently: true });
                            
                            // Fill with black background
                            ctx.fillStyle = 'black';
                            ctx.fillRect(0, 0, canvas.width, canvas.height);
                            
                            // Draw the imported image, scaling to fit if needed
                            const scale = Math.min(
                                originalImage.width / img.width,
                                originalImage.height / img.height
                            );
                            const scaledWidth = img.width * scale;
                            const scaledHeight = img.height * scale;
                            const x = (originalImage.width - scaledWidth) / 2;
                            const y = (originalImage.height - scaledHeight) / 2;
                            
                            ctx.drawImage(img, x, y, scaledWidth, scaledHeight);
                            
                            // Get image data and create mask
                            const imageData = ctx.getImageData(0, 0, originalImage.width, originalImage.height);
                            const mask = new ImageData(originalImage.width, originalImage.height);
                            const maskData = mask.data;
                            const imgData = imageData.data;
                            
                            let pixelCount = 0;
                            
                            // Convert to mask: any non-black pixel becomes white in the mask
                            for (let i = 0; i < imgData.length; i += 4) {
                                // Check if pixel is not black (threshold of 30 to account for compression artifacts)
                                if (imgData[i] > 30 || imgData[i + 1] > 30 || imgData[i + 2] > 30) {
                                    maskData[i] = 255;
                                    maskData[i + 1] = 255;
                                    maskData[i + 2] = 255;
                                    maskData[i + 3] = 255;
                                    pixelCount++;
                                }
                            }
                            
                            // Extract filename without extension for layer name
                            const layerName = file.name.replace(/\.[^/.]+$/, "").replace(/_/g, ' ');
                            
                            // Clear image source to free memory
                            img.src = '';
                            
                            resolve({
                                name: layerName,
                                mask: mask,
                                pixelCount: pixelCount
                            });
                        };
                        img.onerror = () => reject(new Error(`Failed to load ${file.name}`));
                        img.src = event.target.result;
                    };
                    reader.onerror = () => reject(new Error(`Failed to read ${file.name}`));
                    reader.readAsDataURL(file);
                });
                
                // Generate unique color
                const usedColors = new Set(layers.map(l => l.color));
                let color;
                do {
                    color = getRandomColor();
                } while (usedColors.has(color));
                
                const layerId = Date.now() + Math.random();
                const newLayer = {
                    id: layerId,
                    name: layerData.name,
                    color: color,
                    mask: layerData.mask,
                    visible: true,
                    pixelCount: layerData.pixelCount,
                    transform: { x: 0, y: 0, scale: 1, rotation: 0 }
                };
                
                // Add layer immediately to state
                setLayers(currentLayers => [...currentLayers, newLayer]);
                layerHistoryRef.current.set(layerId, { states: [], currentIndex: -1 });
                canvasWorkRef.current.maskCache.set(layerId, layerData.mask);
                
                // Save initial state for undo/redo functionality
                // We need to save the state directly since the layer isn't in the state array yet
                const history = layerHistoryRef.current.get(layerId);
                if (history) {
                    const initialState = new ImageData(layerData.mask.data.slice(), layerData.mask.width, layerData.mask.height);
                    history.states.push(initialState);
                    history.currentIndex = 0;
                }
                
                successCount++;
                
                // Allow browser to breathe between files
                await new Promise(resolve => setTimeout(resolve, 10));
                
            } catch (error) {
                console.error(`Error importing ${file.name}:`, error);
                setStatus(`Failed to import ${file.name}`);
                // Wait a bit before continuing with next file
                await new Promise(resolve => setTimeout(resolve, 100));
            }
        }
        
        if (successCount > 0) {
            setStatus(`Successfully imported ${successCount} of ${files.length} layers`);
            // Select the first imported layer
            setCurrentLayerIndex(firstLayerIndex);
        } else {
            setStatus('Failed to import any layers');
        }
        
        // Reset the file input
        e.target.value = '';
    };
    
    const initializeCanvases = (img) => {
        const canvases = [
            originalCanvasRef.current,
            edgeCanvasRef.current,
            combinedCanvasRef.current,
            currentCanvasRef.current
        ];
        
        canvases.forEach(canvas => {
            if (canvas) {
                canvas.width = img.width;
                canvas.height = img.height;
            }
        });
        
        // Initialize brush canvas
        initBrushCanvas(img);
        
        // Clear context cache when canvas sizes change
        contextsRef.current = {
            original: null,
            edge: null,
            combined: null,
            current: null
        };
        
        const originalCtx = getContext(originalCanvasRef, 'original');
        if (originalCtx) {
            originalCtx.drawImage(img, 0, 0);
        }
        
        // Precompute edges for the new image
        const imageData = originalCtx.getImageData(0, 0, img.width, img.height);
        cachedImageDataRef.current = imageData;
        
        setEdgeProcessing(true);
        // Use setTimeout to avoid blocking the UI
        setTimeout(() => {
            precomputedEdgesRef.current = precomputeEdges(imageData);
            updateEdgeDetection(img);
            setEdgeProcessing(false);
        }, 10);
        
        if (layers.length === 0) {
            createNewLayer();
        }
    };
    
    const updateEdgeDetection = useCallback((img = originalImage) => {
        if (!img || !edgeCanvasRef.current || !precomputedEdgesRef.current) return;
        
        const edgeCtx = getContext(edgeCanvasRef, 'edge');
        
        if (edgeCtx) {
            // Use precomputed edges for instant update
            const edgeData = applyEdgeThreshold(precomputedEdgesRef.current, edgeSensitivity);
            cachedEdgeDataRef.current = edgeData;
            edgeCtx.putImageData(edgeData, 0, 0);
        }
    }, [originalImage, edgeSensitivity, getContext]);
    
    // Precompute edge magnitudes once when image loads
    const precomputeEdges = (imageData) => {
        const width = imageData.width;
        const height = imageData.height;
        const data = imageData.data;
        const magnitudes = new Float32Array(width * height);
        
        
        // Convert to grayscale first (optimization)
        const grayData = new Uint8Array(width * height);
        for (let i = 0; i < width * height; i++) {
            const idx = i * 4;
            grayData[i] = (data[idx] + data[idx + 1] + data[idx + 2]) / 3;
        }
        
        // Compute edge magnitudes
        for (let y = 1; y < height - 1; y++) {
            for (let x = 1; x < width - 1; x++) {
                let pixelX = 0;
                let pixelY = 0;
                
                // Unrolled loop for better performance
                const row0 = (y - 1) * width;
                const row1 = y * width;
                const row2 = (y + 1) * width;
                
                // Apply Sobel operators
                pixelX = -grayData[row0 + x - 1] + grayData[row0 + x + 1]
                       - 2 * grayData[row1 + x - 1] + 2 * grayData[row1 + x + 1]
                       - grayData[row2 + x - 1] + grayData[row2 + x + 1];
                       
                pixelY = -grayData[row0 + x - 1] - 2 * grayData[row0 + x] - grayData[row0 + x + 1]
                       + grayData[row2 + x - 1] + 2 * grayData[row2 + x] + grayData[row2 + x + 1];
                
                magnitudes[y * width + x] = Math.sqrt(pixelX * pixelX + pixelY * pixelY);
            }
        }
        
        return { magnitudes, width, height };
    };
    
    // Fast threshold application using precomputed magnitudes
    const applyEdgeThreshold = (precomputed, threshold) => {
        const { magnitudes, width, height } = precomputed;
        const output = new ImageData(width, height);
        const outputData = output.data;
        
        // Apply threshold in a single pass
        for (let i = 0; i < magnitudes.length; i++) {
            const idx = i * 4;
            if (magnitudes[i] > threshold) {
                outputData[idx] = 255;
                outputData[idx + 1] = 255;
                outputData[idx + 2] = 255;
                outputData[idx + 3] = 255;
            } else {
                outputData[idx] = 0;
                outputData[idx + 1] = 0;
                outputData[idx + 2] = 0;
                outputData[idx + 3] = 255;
            }
        }
        
        return output;
    };
    
    const getRandomColor = () => {
        const colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8', '#FFD93D', '#6BCB77'];
        return colors[Math.floor(Math.random() * colors.length)];
    };
    
    const createNewLayer = () => {
        if (!originalImage) {
            setStatus('Please upload an image first');
            return;
        }
        
        const layerId = Date.now();
        const layerIndex = layers.length;
        const newLayer = {
            id: layerId,
            name: `Layer ${layerIndex + 1}`,
            color: getRandomColor(),
            mask: new ImageData(originalImage.width, originalImage.height),
            visible: true,
            pixelCount: 0,
            transform: { x: 0, y: 0, scale: 1, rotation: 0 }
        };
        
        // Cache the mask for direct manipulation
        canvasWorkRef.current.maskCache.set(layerId, newLayer.mask);
        
        setLayers([...layers, newLayer]);
        layerHistoryRef.current.set(layerId, { states: [], currentIndex: -1 });
        setCurrentLayerIndex(layerIndex);
        
        // Save initial empty state directly to avoid race condition
        const history = layerHistoryRef.current.get(layerId);
        if (history) {
            const initialState = new ImageData(newLayer.mask.data.slice(), newLayer.mask.width, newLayer.mask.height);
            history.states.push(initialState);
            history.currentIndex = 0;
        }
        
        setStatus(`Created ${newLayer.name}`);
    };
    
    const saveLayerState = useCallback((layerId) => {
        const layer = layers.find(l => l.id === layerId);
        if (!layer) return;
        
        const history = layerHistoryRef.current.get(layerId);
        if (!history) return;
        
        // If we're at -1 (empty state), don't truncate, just start fresh
        if (history.currentIndex === -1) {
            history.states = [];
        } else {
            // Truncate any future history when saving a new state
            history.states = history.states.slice(0, history.currentIndex + 1);
        }
        
        // Use the cached mask if available, as it contains the most recent changes
        const cachedMask = canvasWorkRef.current.maskCache.get(layerId);
        const maskToSave = cachedMask || layer.mask;
        const newState = new ImageData(maskToSave.data.slice(), maskToSave.width, maskToSave.height);
        history.states.push(newState);
        
        if (history.states.length > 50) {
            history.states.shift();
            // Don't increment currentIndex if we removed an item
        } else {
            history.currentIndex++;
        }
    }, [layers]);
    
    // Helper to count non-transparent pixels
    const countMaskPixels = useCallback((mask) => {
        let count = 0;
        for (let i = 3; i < mask.data.length; i += 4) {
            if (mask.data[i] > 128) count++;
        }
        return count;
    }, []);
    
    const getTransformedBounds = useCallback((layer, transformMode = 'combined') => {
        let w = layer.mask.width;
        let h = layer.mask.height;
        let totalRotation = 0;
        
        // Apply base transform if needed
        if (transformMode === 'base' || transformMode === 'combined') {
            w *= baseTransform.scale;
            h *= baseTransform.scale;
            totalRotation += baseTransform.rotation;
        }
        
        // Apply layer transform if needed
        if (transformMode === 'layer' || transformMode === 'combined') {
            w *= layer.transform.scale;
            h *= layer.transform.scale;
            totalRotation += layer.transform.rotation;
        }
        
        const angle = totalRotation * Math.PI / 180;
        
        // Calculate rotated bounds
        const cos = Math.abs(Math.cos(angle));
        const sin = Math.abs(Math.sin(angle));
        const width = Math.ceil(w * cos + h * sin);
        const height = Math.ceil(w * sin + h * cos);
        
        return { width, height };
    }, [baseTransform]);
    
    // Calculate required canvas bounds for preview to fit all transformed content
    const calculatePreviewBounds = useCallback((includeCurrentLayer = true, paddingBuffer = 100) => {
        if (!originalImage) return { width: 800, height: 600, offsetX: 0, offsetY: 0 };
        
        // Create a hash of current state for caching
        const layersHash = JSON.stringify(layers.map(l => ({
            id: l.id,
            visible: l.visible,
            transform: l.transform
        })));
        const transformHash = JSON.stringify(baseTransform);
        
        // Check cache
        if (includeCurrentLayer && 
            boundsCache.current.lastLayersHash === layersHash && 
            boundsCache.current.lastBaseTransform === transformHash &&
            boundsCache.current.currentBounds) {
            return boundsCache.current.currentBounds;
        }
        
        if (!includeCurrentLayer && 
            boundsCache.current.lastLayersHash === layersHash && 
            boundsCache.current.lastBaseTransform === transformHash &&
            boundsCache.current.combinedBounds) {
            return boundsCache.current.combinedBounds;
        }
        
        const originalWidth = originalImage.width;
        const originalHeight = originalImage.height;
        let minX = 0, minY = 0, maxX = originalWidth, maxY = originalHeight;
        
        // Get layers to process
        const layersToProcess = includeCurrentLayer && currentLayerIndex >= 0 
            ? [layers[currentLayerIndex]] 
            : layers.filter(layer => layer.visible);
        
        // Calculate bounds for each visible layer
        layersToProcess.forEach(layer => {
            // Calculate transformed dimensions
            const bounds = getTransformedBounds(layer, 'combined');
            
            // Calculate center position with all transforms
            let centerX = originalWidth / 2;
            let centerY = originalHeight / 2;
            
            // Apply base transform position
            centerX += baseTransform.x;
            centerY += baseTransform.y;
            
            // Apply layer transform position  
            centerX += layer.transform.x;
            centerY += layer.transform.y;
            
            // Calculate actual bounds with position
            const left = centerX - bounds.width / 2;
            const right = centerX + bounds.width / 2;
            const top = centerY - bounds.height / 2;
            const bottom = centerY + bounds.height / 2;
            
            // Update overall bounds
            minX = Math.min(minX, left);
            minY = Math.min(minY, top);
            maxX = Math.max(maxX, right);
            maxY = Math.max(maxY, bottom);
        });
        
        // Add padding buffer to keep corners visible
        minX -= paddingBuffer;
        minY -= paddingBuffer;
        maxX += paddingBuffer;
        maxY += paddingBuffer;
        
        const width = Math.ceil(maxX - minX);
        const height = Math.ceil(maxY - minY);
        const offsetX = -minX;  // Offset to translate content into positive space
        const offsetY = -minY;
        
        const result = { width, height, offsetX, offsetY };
        
        // Update cache
        boundsCache.current.lastLayersHash = layersHash;
        boundsCache.current.lastBaseTransform = transformHash;
        if (includeCurrentLayer) {
            boundsCache.current.currentBounds = result;
        } else {
            boundsCache.current.combinedBounds = result;
        }
        
        return result;
    }, [originalImage, currentLayerIndex, layers, baseTransform, getTransformedBounds]);
    
    const updateCurrentCanvas = useCallback(() => {
        if (!currentCanvasRef.current || currentLayerIndex < 0) return;
        
        const ctx = getContext(currentCanvasRef, 'current');
        if (!ctx) return;
        
        let canvasWidth, canvasHeight, contentScale = 1, offsetX = 0, offsetY = 0;
        
        if (isFullscreenMode && currentCanvasRef.current.parentElement) {
            // In fullscreen mode, size canvas to fill container
            const container = currentCanvasRef.current.parentElement;
            const containerRect = container.getBoundingClientRect();
            
            // Account for padding and labels
            const padding = 40;
            canvasWidth = Math.floor(containerRect.width - padding);
            canvasHeight = Math.floor(containerRect.height - padding * 2); // Extra padding for label
            
            // Calculate scale to fit content within the large canvas
            const bounds = calculatePreviewBounds(true, 50);
            const scaleX = canvasWidth / bounds.width;
            const scaleY = canvasHeight / bounds.height;
            contentScale = Math.min(scaleX, scaleY);
            
            // Center the content
            offsetX = (canvasWidth - bounds.width * contentScale) / 2;
            offsetY = (canvasHeight - bounds.height * contentScale) / 2;
            
            // Store for mouse coordinate calculations
            canvasWorkRef.current.contentScale = contentScale;
            canvasWorkRef.current.contentOffset = { x: offsetX, y: offsetY };
            
            // Apply CSS zoom transform for additional user-controlled zoom
            currentCanvasRef.current.style.transform = `scale(${canvasZoom})`;
            currentCanvasRef.current.style.transformOrigin = 'center';
        } else {
            // Normal mode - size based on content
            const bounds = calculatePreviewBounds(true, 50);
            canvasWidth = bounds.width;
            canvasHeight = bounds.height;
            offsetX = bounds.offsetX;
            offsetY = bounds.offsetY;
            
            // Reset transform in normal mode
            currentCanvasRef.current.style.transform = '';
            currentCanvasRef.current.style.transformOrigin = '';
            
            // Reset content scale
            canvasWorkRef.current.contentScale = 1;
            canvasWorkRef.current.contentOffset = { x: 0, y: 0 };
        }
        
        // Only resize if dimensions actually changed
        const needsResize = currentCanvasRef.current.width !== canvasWidth || 
                          currentCanvasRef.current.height !== canvasHeight;
        
        if (needsResize) {
            // Save current canvas content before resizing
            const tempCanvas = document.createElement('canvas');
            tempCanvas.width = currentCanvasRef.current.width;
            tempCanvas.height = currentCanvasRef.current.height;
            const tempCtx = tempCanvas.getContext('2d');
            tempCtx.drawImage(currentCanvasRef.current, 0, 0);
            
            // Resize the canvas (this clears it)
            currentCanvasRef.current.width = canvasWidth;
            currentCanvasRef.current.height = canvasHeight;
            
            // Don't restore old content - we'll redraw everything fresh
        }
        
        ctx.clearRect(0, 0, canvasWidth, canvasHeight);
        
        // Draw original image as background
        if (originalCanvasRef.current && originalImage) {
            ctx.save();
            ctx.globalAlpha = 0.3;
            
            if (isFullscreenMode) {
                // Apply content scaling in fullscreen mode
                ctx.translate(offsetX, offsetY);
                ctx.scale(contentScale, contentScale);
                ctx.drawImage(originalCanvasRef.current, 0, 0);
            } else {
                // Normal mode - use offset directly
                ctx.drawImage(originalCanvasRef.current, offsetX, offsetY);
            }
            
            ctx.restore();
        }
        
        const currentLayer = layers[currentLayerIndex];
        if (currentLayer) {
            ctx.globalAlpha = 1;
            const tempCanvas = document.createElement('canvas');
            tempCanvas.width = currentLayer.mask.width;
            tempCanvas.height = currentLayer.mask.height;
            const tempCtx = tempCanvas.getContext('2d');
            
            const coloredMask = new ImageData(currentLayer.mask.width, currentLayer.mask.height);
            const maskData = currentLayer.mask.data;
            const coloredData = coloredMask.data;
            
            const r = parseInt(currentLayer.color.substr(1, 2), 16);
            const g = parseInt(currentLayer.color.substr(3, 2), 16);
            const b = parseInt(currentLayer.color.substr(5, 2), 16);
            
            for (let i = 0; i < maskData.length; i += 4) {
                if (maskData[i + 3] > 0) {
                    coloredData[i] = r;
                    coloredData[i + 1] = g;
                    coloredData[i + 2] = b;
                    coloredData[i + 3] = maskData[i + 3];
                }
            }
            
            tempCtx.putImageData(coloredMask, 0, 0);
            
            // Apply transforms
            ctx.save();
            
            if (isFullscreenMode) {
                // In fullscreen, apply content scaling first
                ctx.translate(offsetX, offsetY);
                ctx.scale(contentScale, contentScale);
                
                // Then translate to center of scaled content
                const bounds = calculatePreviewBounds(true, 50);
                ctx.translate(bounds.width/2, bounds.height/2);
            } else {
                // Normal mode - translate to canvas center
                const bounds = calculatePreviewBounds(true, 50);
                ctx.translate(bounds.width/2, bounds.height/2);
            }
            
            // Apply base transform
            ctx.translate(baseTransform.x, baseTransform.y);
            ctx.rotate(baseTransform.rotation * Math.PI / 180);
            ctx.scale(baseTransform.scale, baseTransform.scale);
            
            // Apply layer transform (relative to base)
            ctx.translate(currentLayer.transform.x, currentLayer.transform.y);
            ctx.rotate(currentLayer.transform.rotation * Math.PI / 180);
            ctx.scale(currentLayer.transform.scale, currentLayer.transform.scale);
            
            // Draw centered
            ctx.drawImage(tempCanvas, -tempCanvas.width/2, -tempCanvas.height/2);
            ctx.restore();
        }
        
        // Apply perspective transform to the canvas element if in corner mode
        if (originalImage) {
            applyPerspectiveTransform(currentCanvasRef.current, baseTransform.corners, originalImage.width, originalImage.height);
        }
    }, [currentLayerIndex, layers, getContext, calculatePreviewBounds, baseTransform, originalImage, applyPerspectiveTransform, isFullscreenMode, canvasZoom]);
    
    const updateCombinedCanvas = useCallback(() => {
        if (!combinedCanvasRef.current) return;
        
        const ctx = getContext(combinedCanvasRef, 'combined');
        if (!ctx) return;
        
        // Calculate required canvas bounds for all visible layers
        const bounds = calculatePreviewBounds(false, 50); // Include all visible layers with padding
        
        // Only resize if dimensions actually changed
        const needsResize = combinedCanvasRef.current.width !== bounds.width || 
                          combinedCanvasRef.current.height !== bounds.height;
        
        if (needsResize) {
            // Save current canvas content before resizing
            const tempCanvas = document.createElement('canvas');
            tempCanvas.width = combinedCanvasRef.current.width;
            tempCanvas.height = combinedCanvasRef.current.height;
            const tempCtx = tempCanvas.getContext('2d');
            tempCtx.drawImage(combinedCanvasRef.current, 0, 0);
            
            // Resize the canvas (this clears it)
            combinedCanvasRef.current.width = bounds.width;
            combinedCanvasRef.current.height = bounds.height;
            
            // Don't restore old content - we'll redraw everything fresh
        }
        
        ctx.clearRect(0, 0, bounds.width, bounds.height);
        
        // Draw original image as background with offset
        if (originalCanvasRef.current && originalImage) {
            ctx.globalAlpha = 0.5;
            ctx.drawImage(originalCanvasRef.current, bounds.offsetX, bounds.offsetY);
        }
        
        ctx.globalAlpha = 0.7;
        
        // Collect used canvases to release after rendering
        const usedCanvases = [];
        
        layers.forEach(layer => {
            if (layer.visible) {
                // Use pooled canvas instead of creating new one
                const tempCanvas = getPooledCanvas(layer.mask.width, layer.mask.height);
                usedCanvases.push(tempCanvas);
                const tempCtx = tempCanvas.getContext('2d');
                
                const coloredMask = new ImageData(layer.mask.width, layer.mask.height);
                const maskData = layer.mask.data;
                const coloredData = coloredMask.data;
                
                const r = parseInt(layer.color.substr(1, 2), 16);
                const g = parseInt(layer.color.substr(3, 2), 16);
                const b = parseInt(layer.color.substr(5, 2), 16);
                
                for (let i = 0; i < maskData.length; i += 4) {
                    if (maskData[i + 3] > 0) {
                        coloredData[i] = r;
                        coloredData[i + 1] = g;
                        coloredData[i + 2] = b;
                        coloredData[i + 3] = maskData[i + 3];
                    }
                }
                
                tempCtx.putImageData(coloredMask, 0, 0);
                
                // Apply transforms with base transform
                ctx.save();
                // Translate to canvas center plus offset
                ctx.translate(bounds.width/2, bounds.height/2);
                
                // Apply base transform
                ctx.translate(baseTransform.x, baseTransform.y);
                ctx.rotate(baseTransform.rotation * Math.PI / 180);
                ctx.scale(baseTransform.scale, baseTransform.scale);
                
                // Apply layer transform
                ctx.translate(layer.transform.x, layer.transform.y);
                ctx.rotate(layer.transform.rotation * Math.PI / 180);
                ctx.scale(layer.transform.scale, layer.transform.scale);
                
                // Draw centered
                ctx.drawImage(tempCanvas, -tempCanvas.width/2, -tempCanvas.height/2);
                ctx.restore();
            }
        });
        
        // Release all used canvases back to the pool
        usedCanvases.forEach(canvas => releasePooledCanvas(canvas));
        
        // Apply perspective transform to the canvas element if in corner mode
        if (originalImage) {
            applyPerspectiveTransform(combinedCanvasRef.current, baseTransform.corners, originalImage.width, originalImage.height);
        }
    }, [layers, getContext, calculatePreviewBounds, baseTransform, originalImage, applyPerspectiveTransform, getPooledCanvas, releasePooledCanvas]);
    
    // Debounced version of updateCombinedCanvas for brush operations
    const updateCombinedCanvasDebounced = useMemo(
        () => debounce(updateCombinedCanvas, 100), // Update at most 10 times per second
        [updateCombinedCanvas, debounce]
    );
    
    const drawBezierMarkers = useCallback((points) => {
        const ctx = getContext(currentCanvasRef, 'current');
        if (!ctx) return;
        
        // Redraw current canvas first
        updateCurrentCanvas();
        
        // Draw markers and preview line
        ctx.save();
        points.forEach((point, index) => {
            // Draw point marker
            ctx.beginPath();
            ctx.arc(point.x, point.y, 5, 0, 2 * Math.PI);
            ctx.fillStyle = index === 0 || index === 3 ? '#ff4444' : '#4444ff'; // Red for endpoints, blue for control points
            ctx.fill();
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = 2;
            ctx.stroke();
            
            // Draw point number
            ctx.fillStyle = '#ffffff';
            ctx.font = '12px Arial';
            ctx.fillText(index + 1, point.x + 8, point.y - 8);
        });
        
        // Draw preview lines connecting points
        if (points.length > 1) {
            ctx.beginPath();
            ctx.moveTo(points[0].x, points[0].y);
            for (let i = 1; i < points.length; i++) {
                ctx.lineTo(points[i].x, points[i].y);
            }
            ctx.strokeStyle = '#ffff00';
            ctx.lineWidth = 1;
            ctx.setLineDash([5, 5]);
            ctx.stroke();
            ctx.setLineDash([]);
        }
        
        // If we have 3 points, show preview of the curve
        if (points.length === 3) {
            ctx.beginPath();
            ctx.moveTo(points[0].x, points[0].y);
            ctx.quadraticCurveTo(points[1].x, points[1].y, points[2].x, points[2].y);
            ctx.strokeStyle = '#00ff00';
            ctx.lineWidth = 2;
            ctx.stroke();
        }
        
        ctx.restore();
    }, [getContext, updateCurrentCanvas]);

    useEffect(() => {
        updateCurrentCanvas();
        // Use debounced version when drawing to improve performance
        if (isDrawing) {
            updateCombinedCanvasDebounced();
        } else {
            updateCombinedCanvas();
        }
        // Redraw bezier markers if we have points
        if (bezierPoints.length > 0) {
            drawBezierMarkers(bezierPoints);
        }
    }, [layers, currentLayerIndex, updateCurrentCanvas, updateCombinedCanvas, updateCombinedCanvasDebounced, bezierPoints, drawBezierMarkers, isDrawing]);
    
    useEffect(() => {
        // Debounce edge updates for smoother slider experience
        if (edgeUpdateTimerRef.current) {
            clearTimeout(edgeUpdateTimerRef.current);
        }
        
        edgeUpdateTimerRef.current = setTimeout(() => {
            updateEdgeDetection();
        }, 16); // ~60fps
        
        return () => {
            if (edgeUpdateTimerRef.current) {
                clearTimeout(edgeUpdateTimerRef.current);
            }
        };
    }, [edgeSensitivity, updateEdgeDetection]);
    
    // Update canvas when fullscreen mode or zoom changes
    useEffect(() => {
        if (currentLayerIndex >= 0) {
            updateCurrentCanvas();
        }
    }, [isFullscreenMode, canvasZoom, updateCurrentCanvas, currentLayerIndex]);
    
    const toggleLayerVisibility = (index) => {
        const newLayers = [...layers];
        newLayers[index].visible = !newLayers[index].visible;
        setLayers(newLayers);
    };
    
    const selectLayer = (index) => {
        setCurrentLayerIndex(index);
        // Ensure mask cache is synchronized when switching layers
        const layer = layers[index];
        if (layer && !canvasWorkRef.current.maskCache.has(layer.id)) {
            canvasWorkRef.current.maskCache.set(layer.id, layer.mask);
        }
    };
    
    const deleteLayer = (index) => {
        if (layers.length === 1) {
            setStatus('Cannot delete last layer');
            return;
        }
        
        const layer = layers[index];
        
        // Close projection window if open
        if (projectionWindowsRef.current.has(index)) {
            projectionWindowsRef.current.get(index).close();
            projectionWindowsRef.current.delete(index);
        }
        
        const newLayers = layers.filter((_, i) => i !== index);
        setLayers(newLayers);
        layerHistoryRef.current.delete(layer.id);
        canvasWorkRef.current.maskCache.delete(layer.id);
        
        // Update projection window references for remaining layers
        const newProjectionWindows = new Map();
        projectionWindowsRef.current.forEach((window, oldIndex) => {
            if (oldIndex > index) {
                newProjectionWindows.set(oldIndex - 1, window);
            } else if (oldIndex < index) {
                newProjectionWindows.set(oldIndex, window);
            }
        });
        projectionWindowsRef.current = newProjectionWindows;
        
        if (currentLayerIndex >= newLayers.length) {
            setCurrentLayerIndex(newLayers.length - 1);
        }
        
        setStatus(`Deleted ${layer.name}`);
    };
    
    const flattenSelectedLayers = () => {
        const selectedIndices = Array.from(selectedLayers).map(id => 
            layers.findIndex(layer => layer.id === id)
        ).filter(index => index !== -1).sort((a, b) => a - b);
        
        if (selectedIndices.length < 2) {
            setStatus('Select at least 2 layers to flatten');
            return;
        }
        
        // Create a new canvas for the flattened result
        const canvas = document.createElement('canvas');
        canvas.width = originalImage.width;
        canvas.height = originalImage.height;
        const ctx = canvas.getContext('2d', { willReadFrequently: true });
        
        // Clear canvas
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        // Draw each selected layer in order
        selectedIndices.forEach(index => {
            const layer = layers[index];
            const tempCanvas = document.createElement('canvas');
            tempCanvas.width = canvas.width;
            tempCanvas.height = canvas.height;
            const tempCtx = tempCanvas.getContext('2d');
            
            // Draw the layer mask
            tempCtx.fillStyle = layer.color;
            tempCtx.globalAlpha = layer.opacity;
            
            const maskData = new ImageData(
                new Uint8ClampedArray(layer.mask),
                canvas.width,
                canvas.height
            );
            
            const maskCanvas = document.createElement('canvas');
            maskCanvas.width = canvas.width;
            maskCanvas.height = canvas.height;
            const maskCtx = maskCanvas.getContext('2d');
            maskCtx.putImageData(maskData, 0, 0);
            
            tempCtx.globalCompositeOperation = 'source-over';
            tempCtx.fillRect(0, 0, canvas.width, canvas.height);
            tempCtx.globalCompositeOperation = 'destination-in';
            tempCtx.drawImage(maskCanvas, 0, 0);
            
            // Apply layer transform
            ctx.save();
            ctx.translate(canvas.width / 2, canvas.height / 2);
            ctx.translate(layer.transform.x, layer.transform.y);
            ctx.scale(layer.transform.scale, layer.transform.scale);
            ctx.rotate((layer.transform.rotation * Math.PI) / 180);
            ctx.translate(-canvas.width / 2, -canvas.height / 2);
            
            ctx.drawImage(tempCanvas, 0, 0);
            ctx.restore();
        });
        
        // Create new flattened layer
        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        const flattenedMask = new Uint8Array(canvas.width * canvas.height);
        
        // Extract alpha channel as mask
        for (let i = 0; i < imageData.data.length; i += 4) {
            const alpha = imageData.data[i + 3];
            const maskIndex = i / 4;
            flattenedMask[maskIndex] = alpha;
        }
        
        // Get names of layers being flattened
        const layerNames = selectedIndices.map(i => layers[i].name).join(' + ');
        const newLayerName = `Flattened: ${layerNames}`;
        
        const newLayer = {
            id: Date.now().toString(),
            name: newLayerName,
            mask: flattenedMask,
            color: '#ffffff',
            opacity: 1,
            visible: true,
            transform: { x: 0, y: 0, scale: 1, rotation: 0 }
        };
        
        // Remove the selected layers (in reverse order to maintain indices)
        const remainingLayers = layers.filter((_, index) => !selectedIndices.includes(index));
        
        // Close projection windows for deleted layers
        selectedIndices.forEach(index => {
            if (projectionWindowsRef.current.has(index)) {
                projectionWindowsRef.current.get(index).close();
                projectionWindowsRef.current.delete(index);
            }
        });
        
        // Add the new flattened layer
        const newLayers = [...remainingLayers, newLayer];
        setLayers(newLayers);
        
        // Clear selection
        setSelectedLayers(new Set());
        
        // Set the new layer as current
        setCurrentLayerIndex(newLayers.length - 1);
        
        setStatus(`Flattened ${selectedIndices.length} layers into "${newLayerName}"`);
    };
    
    const downloadLayer = (index, transformMode = 'combined') => {
        // transformMode: 'none', 'layer', 'base', 'combined'
        const layer = layers[index];
        const tempCanvas = document.createElement('canvas');
        
        if (transformMode !== 'none') {
            // Calculate bounds based on transform mode
            const bounds = getTransformedBounds(layer, transformMode);
            tempCanvas.width = bounds.width;
            tempCanvas.height = bounds.height;
            const tempCtx = tempCanvas.getContext('2d');
            
            // Black background
            tempCtx.fillStyle = 'black';
            tempCtx.fillRect(0, 0, tempCanvas.width, tempCanvas.height);
            
            // Apply transforms from center
            tempCtx.save();
            tempCtx.translate(tempCanvas.width/2, tempCanvas.height/2);
            
            // Apply base transform if needed
            if (transformMode === 'base' || transformMode === 'combined') {
                tempCtx.translate(baseTransform.x, baseTransform.y);
                tempCtx.rotate(baseTransform.rotation * Math.PI / 180);
                tempCtx.scale(baseTransform.scale, baseTransform.scale);
            }
            
            // Apply layer transform if needed
            if (transformMode === 'layer' || transformMode === 'combined') {
                tempCtx.translate(layer.transform.x, layer.transform.y);
                tempCtx.rotate(layer.transform.rotation * Math.PI / 180);
                tempCtx.scale(layer.transform.scale, layer.transform.scale);
            }
            
            // Create white mask
            const maskCanvas = document.createElement('canvas');
            maskCanvas.width = layer.mask.width;
            maskCanvas.height = layer.mask.height;
            const maskCtx = maskCanvas.getContext('2d');
            
            const whiteMask = new ImageData(layer.mask.width, layer.mask.height);
            for (let i = 0; i < layer.mask.data.length; i += 4) {
                if (layer.mask.data[i + 3] > 0) {
                    whiteMask.data[i] = 255;
                    whiteMask.data[i + 1] = 255;
                    whiteMask.data[i + 2] = 255;
                    whiteMask.data[i + 3] = 255;
                }
            }
            maskCtx.putImageData(whiteMask, 0, 0);
            
            // Draw centered
            tempCtx.drawImage(maskCanvas, -maskCanvas.width/2, -maskCanvas.height/2);
            tempCtx.restore();
        } else {
            // Original size without transform
            tempCanvas.width = layer.mask.width;
            tempCanvas.height = layer.mask.height;
            const tempCtx = tempCanvas.getContext('2d');
            
            tempCtx.fillStyle = 'black';
            tempCtx.fillRect(0, 0, tempCanvas.width, tempCanvas.height);
            
            const whiteMask = new ImageData(layer.mask.width, layer.mask.height);
            for (let i = 0; i < layer.mask.data.length; i += 4) {
                if (layer.mask.data[i + 3] > 0) {
                    whiteMask.data[i] = 255;
                    whiteMask.data[i + 1] = 255;
                    whiteMask.data[i + 2] = 255;
                    whiteMask.data[i + 3] = 255;
                }
            }
            tempCtx.putImageData(whiteMask, 0, 0);
        }
        
        const link = document.createElement('a');
        const suffix = transformMode === 'none' ? '' : '_' + transformMode;
        link.download = layer.name.replace(/[^a-z0-9]/gi, '_') + suffix + '.png';
        link.href = tempCanvas.toDataURL();
        link.click();
        
        setStatus(`Downloaded ${layer.name}`);
    };
    
    
    const downloadAllLayers = () => {
        let downloadIndex = 0;
        
        function downloadNext() {
            if (downloadIndex < layers.length) {
                downloadLayer(downloadIndex, 'combined');
                downloadIndex++;
                setTimeout(downloadNext, 500);
            }
        }
        
        downloadNext();
        setStatus('Downloading all layers...');
    };
    
    const openBaseTransformWindow = () => {
        if (!originalImage) {
            setStatus('Please upload an image first');
            return;
        }
        
        const projWindow = window.open('/backend-static/projection_window.html', 'base_transform', 'width=800,height=600');
        
        projWindow.onload = () => {
            // Get the original image data
            const tempCanvas = document.createElement('canvas');
            tempCanvas.width = originalImage.width;
            tempCanvas.height = originalImage.height;
            const tempCtx = tempCanvas.getContext('2d', { willReadFrequently: true });
            tempCtx.drawImage(originalImage, 0, 0);
            const imageData = tempCtx.getImageData(0, 0, originalImage.width, originalImage.height);
            
            // Create a layer that contains the actual image data
            const imageLayer = {
                id: 'base',
                name: 'Base Transform (Original Image)',
                mask: imageData, // This contains the actual image data, not a mask
                transform: { x: 0, y: 0, scale: 1, rotation: 0 } // Base gets identity layer transform
            };
            
            projWindow.postMessage({
                type: 'init',
                layer: imageLayer,
                layerIndex: -1, // Special index for base transform
                baseTransform: baseTransform,
                isBaseTransformMode: true,
                showAsImage: true, // Tell projection window to show as image, not mask
                originalImageDimensions: {
                    width: originalImage.width,
                    height: originalImage.height
                }
            }, '*');
        };
        
        setStatus('Opened base transform window');
    };
    
    const resetBaseTransform = () => {
        const defaultCorners = originalImage ? {
            topLeft: { x: 0, y: 0 },
            topRight: { x: originalImage.width, y: 0 },
            bottomLeft: { x: 0, y: originalImage.height },
            bottomRight: { x: originalImage.width, y: originalImage.height }
        } : {
            topLeft: { x: 0, y: 0 },
            topRight: { x: 1000, y: 0 },
            bottomLeft: { x: 0, y: 600 },
            bottomRight: { x: 1000, y: 600 }
        };
        
        setBaseTransform({ 
            mode: 'basic',
            x: 0, y: 0, scale: 1, rotation: 0,
            corners: defaultCorners
        });
        setStatus('Reset base transform');
    };
    
    const openFullscreenEditor = (index) => {
        const layer = layers[index];
        const canvas = document.createElement('canvas');
        canvas.width = originalImage.width;
        canvas.height = originalImage.height;
        const ctx = canvas.getContext('2d');
        
        // Convert single-channel mask to RGBA ImageData
        const maskSize = canvas.width * canvas.height;
        const rgbaData = new Uint8ClampedArray(maskSize * 4);
        
        for (let i = 0; i < maskSize; i++) {
            const alpha = layer.mask[i] || 0;
            rgbaData[i * 4] = 255;     // R
            rgbaData[i * 4 + 1] = 255; // G
            rgbaData[i * 4 + 2] = 255; // B
            rgbaData[i * 4 + 3] = alpha; // A
        }
        
        const maskData = new ImageData(rgbaData, canvas.width, canvas.height);
        ctx.putImageData(maskData, 0, 0);
        
        // Convert to data URL
        const dataUrl = canvas.toDataURL('image/png');
        
        // Create fullscreen editor HTML
        const editorHtml = `
<!DOCTYPE html>
<html>
<head>
    <title>Layer Editor - ${layer.name}</title>
    <style>
        body {
            margin: 0;
            padding: 0;
            background: #1a1a1a;
            overflow: hidden;
            font-family: Arial, sans-serif;
        }
        #canvas-container {
            position: absolute;
            top: 60px;
            left: 0;
            right: 0;
            bottom: 0;
            display: flex;
            justify-content: center;
            align-items: center;
            overflow: auto;
        }
        #editor-canvas {
            background: #2a2a2a;
            box-shadow: 0 0 20px rgba(0,0,0,0.5);
            cursor: none;
            image-rendering: pixelated;
        }
        #toolbar {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            height: 60px;
            background: #222;
            color: white;
            display: flex;
            align-items: center;
            padding: 0 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.3);
            z-index: 100;
        }
        .tool-group {
            display: flex;
            align-items: center;
            margin-right: 30px;
        }
        .tool-button {
            background: #444;
            color: white;
            border: none;
            padding: 8px 16px;
            margin: 0 5px;
            cursor: pointer;
            border-radius: 4px;
        }
        .tool-button.active {
            background: #2196F3;
        }
        .tool-button:hover {
            background: #555;
        }
        .tool-button.active:hover {
            background: #1976D2;
        }
        input[type="range"] {
            width: 150px;
            margin: 0 10px;
        }
        #cursor-preview {
            position: fixed;
            border: 2px solid white;
            border-radius: 50%;
            pointer-events: none;
            mix-blend-mode: difference;
        }
        #zoom-info {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: rgba(0,0,0,0.8);
            color: white;
            padding: 10px;
            border-radius: 4px;
        }
        label {
            margin-right: 5px;
        }
    </style>
</head>
<body>
    <div id="toolbar">
        <div class="tool-group">
            <button class="tool-button active" data-tool="brush">Brush</button>
            <button class="tool-button" data-tool="eraser">Eraser</button>
        </div>
        <div class="tool-group">
            <label>Size:</label>
            <input type="range" id="brush-size" min="1" max="200" value="10">
            <span id="size-display">10</span>
        </div>
        <div class="tool-group">
            <label>Zoom:</label>
            <input type="range" id="zoom" min="10" max="500" value="100" step="10">
            <span id="zoom-display">100%</span>
        </div>
        <div class="tool-group">
            <button class="tool-button" id="save-btn">Save & Close</button>
            <button class="tool-button" id="cancel-btn">Cancel</button>
        </div>
    </div>
    
    <div id="canvas-container">
        <canvas id="editor-canvas"></canvas>
    </div>
    
    <div id="cursor-preview"></div>
    <div id="zoom-info"></div>
    
    <script>
        const canvas = document.getElementById('editor-canvas');
        const ctx = canvas.getContext('2d', { willReadFrequently: true });
        const container = document.getElementById('canvas-container');
        const cursorPreview = document.getElementById('cursor-preview');
        const zoomInfo = document.getElementById('zoom-info');
        
        let currentTool = 'brush';
        let brushSize = 10;
        let zoom = 1;
        let isDrawing = false;
        let lastPos = null;
        let hasChanges = false;
        
        // Load the layer mask
        const img = new Image();
        img.onload = function() {
            canvas.width = img.width;
            canvas.height = img.height;
            ctx.drawImage(img, 0, 0);
            updateCanvasSize();
        };
        img.src = '${dataUrl}';
        
        // Tool selection
        document.querySelectorAll('[data-tool]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                document.querySelectorAll('[data-tool]').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                currentTool = btn.dataset.tool;
            });
        });
        
        // Brush size
        const sizeSlider = document.getElementById('brush-size');
        const sizeDisplay = document.getElementById('size-display');
        sizeSlider.addEventListener('input', (e) => {
            brushSize = parseInt(e.target.value);
            sizeDisplay.textContent = brushSize;
            updateCursorPreview();
        });
        
        // Zoom
        const zoomSlider = document.getElementById('zoom');
        const zoomDisplay = document.getElementById('zoom-display');
        zoomSlider.addEventListener('input', (e) => {
            zoom = parseInt(e.target.value) / 100;
            zoomDisplay.textContent = e.target.value + '%';
            updateCanvasSize();
            updateZoomInfo();
        });
        
        function updateCanvasSize() {
            canvas.style.width = (canvas.width * zoom) + 'px';
            canvas.style.height = (canvas.height * zoom) + 'px';
        }
        
        function updateZoomInfo() {
            const rect = canvas.getBoundingClientRect();
            zoomInfo.textContent = \`Canvas: \${canvas.width}x\${canvas.height} | Display: \${Math.round(rect.width)}x\${Math.round(rect.height)}\`;
        }
        
        function updateCursorPreview() {
            const size = brushSize * zoom * 2;
            cursorPreview.style.width = size + 'px';
            cursorPreview.style.height = size + 'px';
        }
        
        // Drawing functions
        function getMousePos(e) {
            const rect = canvas.getBoundingClientRect();
            return {
                x: Math.floor((e.clientX - rect.left) / zoom),
                y: Math.floor((e.clientY - rect.top) / zoom)
            };
        }
        
        function drawLine(x0, y0, x1, y1) {
            const dx = Math.abs(x1 - x0);
            const dy = Math.abs(y1 - y0);
            const sx = (x0 < x1) ? 1 : -1;
            const sy = (y0 < y1) ? 1 : -1;
            let err = dx - dy;
            
            while (true) {
                drawBrush(x0, y0);
                
                if ((x0 === x1) && (y0 === y1)) break;
                const e2 = 2 * err;
                if (e2 > -dy) { err -= dy; x0 += sx; }
                if (e2 < dx) { err += dx; y0 += sy; }
            }
        }
        
        function drawBrush(x, y) {
            ctx.globalCompositeOperation = currentTool === 'eraser' ? 'destination-out' : 'source-over';
            ctx.fillStyle = 'white';
            ctx.beginPath();
            ctx.arc(x, y, brushSize, 0, Math.PI * 2);
            ctx.fill();
            hasChanges = true;
        }
        
        // Mouse events
        canvas.addEventListener('mousedown', (e) => {
            isDrawing = true;
            const pos = getMousePos(e);
            lastPos = pos;
            drawBrush(pos.x, pos.y);
        });
        
        canvas.addEventListener('mousemove', (e) => {
            const pos = getMousePos(e);
            
            // Update cursor
            cursorPreview.style.left = (e.clientX - brushSize * zoom) + 'px';
            cursorPreview.style.top = (e.clientY - brushSize * zoom) + 'px';
            
            if (isDrawing && lastPos) {
                drawLine(lastPos.x, lastPos.y, pos.x, pos.y);
                lastPos = pos;
            }
        });
        
        canvas.addEventListener('mouseup', () => {
            isDrawing = false;
            lastPos = null;
        });
        
        canvas.addEventListener('mouseleave', () => {
            isDrawing = false;
            lastPos = null;
            cursorPreview.style.display = 'none';
        });
        
        canvas.addEventListener('mouseenter', () => {
            cursorPreview.style.display = 'block';
            updateCursorPreview();
        });
        
        // Save functionality
        document.getElementById('save-btn').addEventListener('click', () => {
            if (hasChanges && window.opener && !window.opener.closed) {
                const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                const maskData = new Uint8Array(canvas.width * canvas.height);
                
                // Extract alpha channel as mask
                for (let i = 0; i < imageData.data.length; i += 4) {
                    maskData[i / 4] = imageData.data[i + 3];
                }
                
                window.opener.postMessage({
                    type: 'updateLayerMask',
                    layerIndex: ${index},
                    maskData: Array.from(maskData),
                    width: canvas.width,
                    height: canvas.height
                }, '*');
            }
            window.close();
        });
        
        document.getElementById('cancel-btn').addEventListener('click', () => {
            if (hasChanges && !confirm('Discard changes?')) return;
            window.close();
        });
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.key === 'b') {
                document.querySelector('[data-tool="brush"]').click();
            } else if (e.key === 'e') {
                document.querySelector('[data-tool="eraser"]').click();
            } else if (e.key === '[') {
                sizeSlider.value = Math.max(1, brushSize - 5);
                sizeSlider.dispatchEvent(new Event('input'));
            } else if (e.key === ']') {
                sizeSlider.value = Math.min(200, brushSize + 5);
                sizeSlider.dispatchEvent(new Event('input'));
            } else if (e.key === 'Escape') {
                document.getElementById('cancel-btn').click();
            }
        });
        
        // Initial setup
        updateCursorPreview();
        updateZoomInfo();
    </script>
</body>
</html>
        `;
        
        // Open fullscreen editor window
        const editorWindow = window.open('', `layer_editor_${index}`, 'width=1200,height=800');
        editorWindow.document.write(editorHtml);
        editorWindow.document.close();
        
        // Store reference
        projectionWindowsRef.current.set(index, editorWindow);
    };
    
    const openProjectionWindow = (index) => {
        const layer = layers[index];
        
        if (projectionWindowsRef.current.has(index)) {
            projectionWindowsRef.current.get(index).close();
        }
        
        const projWindow = window.open('/backend-static/projection_window.html', `projection_${index}`, 'width=800,height=600');
        projectionWindowsRef.current.set(index, projWindow);
        
        projWindow.onload = () => {
            projWindow.postMessage({
                type: 'init',
                layer: layer,
                layerIndex: index,
                baseTransform: baseTransform
            }, '*');
        };
        
        setStatus(`Opened projection window for ${layer.name}`);
    };
    
    const handleCanvasMouseDown = (e) => {
        // Get the actual canvas that was clicked
        const canvas = e.currentTarget;
        const rect = canvas.getBoundingClientRect();
        
        // Calculate scale factors between displayed size and internal resolution
        let scaleX = canvas.width / rect.width;
        let scaleY = canvas.height / rect.height;
        
        // In fullscreen mode, we need to account for the CSS transform scale
        if (isFullscreenMode && canvas === currentCanvasRef.current && canvasZoom !== 1) {
            scaleX = scaleX / canvasZoom;
            scaleY = scaleY / canvasZoom;
        }
        
        // Apply scaling to get correct canvas coordinates
        let x = Math.floor((e.clientX - rect.left) * scaleX);
        let y = Math.floor((e.clientY - rect.top) * scaleY);
        
        // In fullscreen mode with content scaling, adjust coordinates
        if (isFullscreenMode && canvas === currentCanvasRef.current && canvasWorkRef.current.contentScale !== 1) {
            // Remove the content offset and scale to get coordinates in original image space
            x = (x - canvasWorkRef.current.contentOffset.x) / canvasWorkRef.current.contentScale;
            y = (y - canvasWorkRef.current.contentOffset.y) / canvasWorkRef.current.contentScale;
        }
        
        // Handle selection tool
        if (currentTool === 'select') {
            setIsSelecting(true);
            setSelectionStart({ x, y });
            setSelection(null);
            return;
        }
        
        if (currentLayerIndex < 0) return;
        
        // Transform coordinates to layer space if we have transformations
        const currentLayer = layers[currentLayerIndex];
        if (currentLayer && (
            currentLayer.transform.rotation !== 0 || 
            currentLayer.transform.scale !== 1 ||
            currentLayer.transform.x !== 0 ||
            currentLayer.transform.y !== 0 ||
            baseTransform.rotation !== 0 ||
            baseTransform.scale !== 1 ||
            baseTransform.x !== 0 ||
            baseTransform.y !== 0
        )) {
            const transformed = transformMouseToLayer(x, y, currentLayer);
            x = transformed.x;
            y = transformed.y;
        }
        
        // For edge detection canvas, we need to apply the selection to the current layer
        const isEdgeCanvas = canvas === edgeCanvasRef.current;
        
        if (currentTool === 'floodFill') {
            smartFloodFill(x, y, isEdgeCanvas);
        } else if (currentTool === 'magicWand') {
            magicWandFloodFill(x, y, isEdgeCanvas);
        } else if (currentTool === 'despeckle') {
            despeckleLayer();
        } else if (currentTool === 'brush' || currentTool === 'eraser') {
            setIsDrawing(true);
            lastBrushPosRef.current = null; // Reset for new stroke
            drawBrush(x, y);
        } else if (currentTool === 'bezier') {
            const newPoints = [...bezierPoints, {x, y}];
            setBezierPoints(newPoints);
            
            // Draw temporary markers for bezier points
            drawBezierMarkers(newPoints);
            
            if (newPoints.length === 4) {
                drawBezier(newPoints);
                setBezierPoints([]);
            }
        }
    };
    
    const handleCanvasMouseMove = (e) => {
        const canvas = e.currentTarget;
        const rect = canvas.getBoundingClientRect();
        
        // Calculate scale factors between displayed size and internal resolution
        let scaleX = canvas.width / rect.width;
        let scaleY = canvas.height / rect.height;
        
        // In fullscreen mode, we need to account for the CSS transform scale
        if (isFullscreenMode && canvas === currentCanvasRef.current && canvasZoom !== 1) {
            scaleX = scaleX / canvasZoom;
            scaleY = scaleY / canvasZoom;
        }
        
        // Apply scaling to get correct canvas coordinates
        let x = Math.floor((e.clientX - rect.left) * scaleX);
        let y = Math.floor((e.clientY - rect.top) * scaleY);
        
        // In fullscreen mode with content scaling, adjust coordinates
        if (isFullscreenMode && canvas === currentCanvasRef.current && canvasWorkRef.current.contentScale !== 1) {
            // Remove the content offset and scale to get coordinates in original image space
            x = (x - canvasWorkRef.current.contentOffset.x) / canvasWorkRef.current.contentScale;
            y = (y - canvasWorkRef.current.contentOffset.y) / canvasWorkRef.current.contentScale;
        }
        
        // Handle selection drawing
        if (isSelecting && selectionStart) {
            const left = Math.min(selectionStart.x, x);
            const top = Math.min(selectionStart.y, y);
            const width = Math.abs(x - selectionStart.x);
            const height = Math.abs(y - selectionStart.y);
            
            setSelection({ x: left, y: top, width, height });
            
            // Update visual feedback
            requestAnimationFrame(() => {
                drawSelectionPreview();
            });
            
            return;
        }
        
        // Transform coordinates for drawing operations
        let drawX = x;
        let drawY = y;
        
        if (currentLayerIndex >= 0) {
            const currentLayer = layers[currentLayerIndex];
            if (currentLayer && (
                currentLayer.transform.rotation !== 0 || 
                currentLayer.transform.scale !== 1 ||
                currentLayer.transform.x !== 0 ||
                currentLayer.transform.y !== 0 ||
                baseTransform.rotation !== 0 ||
                baseTransform.scale !== 1 ||
                baseTransform.x !== 0 ||
                baseTransform.y !== 0
            )) {
                const transformed = transformMouseToLayer(x, y, currentLayer);
                drawX = transformed.x;
                drawY = transformed.y;
            }
        }
        
        // Update cursor position for preview (both screen and canvas coordinates)
        setCursorPosition({ 
            x: e.clientX - rect.left, 
            y: e.clientY - rect.top,
            canvasX: x,
            canvasY: y,
            visible: true,
            activeCanvas: canvas
        });
        
        if (!isDrawing || currentLayerIndex < 0) return;
        
        if (currentTool === 'brush' || currentTool === 'eraser') {
            drawBrush(drawX, drawY);
        }
    };
    
    const handleCanvasMouseUp = () => {
        if (isSelecting && selection) {
            setIsSelecting(false);
            // Capture selection data
            if (currentLayerIndex >= 0 && selection.width > 0 && selection.height > 0) {
                captureSelection();
            }
        }
        
        if (isDrawing) {
            setIsDrawing(false);
            
            // Clear brush canvas for next stroke
            if (brushCtxRef.current) {
                brushCtxRef.current.clearRect(0, 0, brushCanvasRef.current.width, brushCanvasRef.current.height);
            }
            lastBrushPosRef.current = null;
            
            // Ensure any pending brush updates are flushed
            if (brushUpdateTimerRef.current) {
                clearTimeout(brushUpdateTimerRef.current);
                flushBrushToMask();
            }
            
            saveLayerState(layers[currentLayerIndex].id);
        }
    };
    
    const handleCanvasMouseLeave = () => {
        setCursorPosition({ x: 0, y: 0, canvasX: 0, canvasY: 0, visible: false, activeCanvas: null });
        if (isDrawing) {
            setIsDrawing(false);
            
            // Clear brush canvas
            if (brushCtxRef.current) {
                brushCtxRef.current.clearRect(0, 0, brushCanvasRef.current.width, brushCanvasRef.current.height);
            }
            lastBrushPosRef.current = null;
            
            // Flush any pending updates
            if (brushUpdateTimerRef.current) {
                clearTimeout(brushUpdateTimerRef.current);
                flushBrushToMask();
            }
            
            saveLayerState(layers[currentLayerIndex].id);
        }
        
        if (isSelecting) {
            setIsSelecting(false);
            setSelection(null);
        }
    };
    
    // Draw selection rectangle preview
    const drawSelectionPreview = () => {
        if (!selection || !currentCanvasRef.current) return;
        
        const ctx = getContext(currentCanvasRef, 'current');
        if (!ctx) return;
        
        // Redraw current layer first
        updateCurrentCanvas();
        
        // Draw selection rectangle
        ctx.save();
        ctx.strokeStyle = '#3498db';
        ctx.lineWidth = 2;
        ctx.setLineDash([5, 5]);
        ctx.strokeRect(selection.x, selection.y, selection.width, selection.height);
        ctx.restore();
    };
    
    // Capture selection data from current layer
    const captureSelection = () => {
        if (!selection || currentLayerIndex < 0) return;
        
        const layer = layers[currentLayerIndex];
        const mask = canvasWorkRef.current.maskCache.get(layer.id) || layer.mask;
        
        // Create ImageData for selected region
        const selectionData = new ImageData(selection.width, selection.height);
        const maskData = mask.data;
        const selData = selectionData.data;
        
        // Copy pixels from selection area
        for (let y = 0; y < selection.height; y++) {
            for (let x = 0; x < selection.width; x++) {
                const srcIdx = ((selection.y + y) * originalImage.width + (selection.x + x)) * 4;
                const destIdx = (y * selection.width + x) * 4;
                
                selData[destIdx] = maskData[srcIdx];
                selData[destIdx + 1] = maskData[srcIdx + 1];
                selData[destIdx + 2] = maskData[srcIdx + 2];
                selData[destIdx + 3] = maskData[srcIdx + 3];
            }
        }
        
        setSelection({
            ...selection,
            data: selectionData
        });
        
        setStatus('Selection captured - Use Ctrl/Cmd+C to copy, Ctrl/Cmd+X to cut, Ctrl/Cmd+V to paste');
    };
    
    // Copy selection to clipboard
    const copySelection = useCallback(() => {
        if (!selection || !selection.data) {
            setStatus('No selection to copy');
            return;
        }
        
        setClipboard({
            width: selection.width,
            height: selection.height,
            data: new ImageData(selection.data.data.slice(), selection.width, selection.height)
        });
        
        setStatus('Selection copied');
    }, [selection]);
    
    // Delete selection content
    const deleteSelection = useCallback(() => {
        if (!selection || currentLayerIndex < 0) {
            setStatus('No selection to delete');
            return;
        }
        
        const layer = layers[currentLayerIndex];
        let cachedMask = canvasWorkRef.current.maskCache.get(layer.id);
        if (!cachedMask) {
            cachedMask = new ImageData(layer.mask.data.slice(), originalImage.width, originalImage.height);
            canvasWorkRef.current.maskCache.set(layer.id, cachedMask);
        }
        
        const maskData = cachedMask.data;
        
        // Clear pixels in selection area
        for (let y = 0; y < selection.height; y++) {
            for (let x = 0; x < selection.width; x++) {
                const idx = ((selection.y + y) * originalImage.width + (selection.x + x)) * 4;
                maskData[idx] = 0;
                maskData[idx + 1] = 0;
                maskData[idx + 2] = 0;
                maskData[idx + 3] = 0;
            }
        }
        
        // Update layer
        canvasWorkRef.current.pendingUpdates.push({
            layerId: layer.id,
            changes: {
                mask: cachedMask,
                pixelCount: countMaskPixels(cachedMask)
            }
        });
        
        flushPendingUpdates();
        updateCurrentCanvas();
        saveLayerState(layer.id);
        
        setSelection(null);
        setStatus('Selection deleted');
    }, [selection, currentLayerIndex, layers, originalImage, flushPendingUpdates, saveLayerState, updateCurrentCanvas, countMaskPixels]);
    
    // Cut selection (copy and delete)
    const cutSelection = useCallback(() => {
        if (!selection || !selection.data || currentLayerIndex < 0) {
            setStatus('No selection to cut');
            return;
        }
        
        copySelection();
        deleteSelection();
    }, [selection, currentLayerIndex, copySelection, deleteSelection]);
    
    // Paste from clipboard
    const pasteFromClipboard = useCallback((x = 0, y = 0) => {
        if (!clipboard || currentLayerIndex < 0) {
            setStatus('Nothing to paste');
            return;
        }
        
        const layer = layers[currentLayerIndex];
        let cachedMask = canvasWorkRef.current.maskCache.get(layer.id);
        if (!cachedMask) {
            cachedMask = new ImageData(layer.mask.data.slice(), originalImage.width, originalImage.height);
            canvasWorkRef.current.maskCache.set(layer.id, cachedMask);
        }
        
        const maskData = cachedMask.data;
        const clipData = clipboard.data.data;
        
        // Paste pixels at position
        for (let py = 0; py < clipboard.height; py++) {
            for (let px = 0; px < clipboard.width; px++) {
                const destX = x + px;
                const destY = y + py;
                
                if (destX >= 0 && destX < originalImage.width && 
                    destY >= 0 && destY < originalImage.height) {
                    const srcIdx = (py * clipboard.width + px) * 4;
                    const destIdx = (destY * originalImage.width + destX) * 4;
                    
                    if (clipData[srcIdx + 3] > 0) {
                        maskData[destIdx] = clipData[srcIdx];
                        maskData[destIdx + 1] = clipData[srcIdx + 1];
                        maskData[destIdx + 2] = clipData[srcIdx + 2];
                        maskData[destIdx + 3] = clipData[srcIdx + 3];
                    }
                }
            }
        }
        
        // Update layer
        canvasWorkRef.current.pendingUpdates.push({
            layerId: layer.id,
            changes: {
                mask: cachedMask,
                pixelCount: countMaskPixels(cachedMask)
            }
        });
        
        flushPendingUpdates();
        updateCurrentCanvas();
        saveLayerState(layer.id);
        
        setStatus('Pasted from clipboard');
    }, [clipboard, currentLayerIndex, layers, originalImage, flushPendingUpdates, updateCurrentCanvas, saveLayerState, countMaskPixels]);
    
    // Paste selection (wrapper for keyboard shortcut)
    const pasteSelection = useCallback(() => {
        if (!clipboard) {
            setStatus('Nothing to paste');
            return;
        }
        
        // Paste at center of canvas
        const centerX = Math.floor((originalImage.width - clipboard.width) / 2);
        const centerY = Math.floor((originalImage.height - clipboard.height) / 2);
        
        pasteFromClipboard(centerX, centerY);
    }, [clipboard, originalImage, pasteFromClipboard]);
    
    const smartFloodFill = (startX, startY, fromEdgeCanvas = false) => {
        const layer = layers[currentLayerIndex];
        const width = originalImage.width;
        const height = originalImage.height;
        
        // Mark as processing
        canvasWorkRef.current.isProcessing = true;
        
        const visited = new Uint8Array(width * height);
        const stack = [{x: startX, y: startY}];
        // Use cached data if available, otherwise get fresh data
        const originalData = cachedImageDataRef.current ? cachedImageDataRef.current.data : 
            getContext(originalCanvasRef, 'original').getImageData(0, 0, width, height).data;
        
        // For edge detection, use precomputed magnitudes if available
        let isEdge;
        if (precomputedEdgesRef.current && fromEdgeCanvas) {
            const { magnitudes } = precomputedEdgesRef.current;
            isEdge = (idx) => magnitudes[idx] > edgeSensitivity;
        } else {
            const edgeData = cachedEdgeDataRef.current ? cachedEdgeDataRef.current.data :
                getContext(edgeCanvasRef, 'edge').getImageData(0, 0, width, height).data;
            isEdge = (idx) => edgeData[idx * 4] > 128;
        }
        
        // Work directly on cached mask if available, otherwise clone
        let maskData;
        const cachedMask = canvasWorkRef.current.maskCache.get(layer.id);
        if (cachedMask) {
            maskData = cachedMask.data;
        } else {
            const newMask = new ImageData(layer.mask.data.slice(), width, height);
            maskData = newMask.data;
            canvasWorkRef.current.maskCache.set(layer.id, newMask);
        }
        
        const startIdx = (startY * width + startX) * 4;
        const startColor = [originalData[startIdx], originalData[startIdx + 1], originalData[startIdx + 2]];
        
        let pixelCount = 0;
        const toleranceValue = tolerance * 3;
        
        // Use a more efficient stack-based approach with batch processing
        const batchSize = 100;
        let batch = 0;
        
        while (stack.length > 0) {
            const {x, y} = stack.pop();
            
            if (x < 0 || x >= width || y < 0 || y >= height) continue;
            
            const idx = y * width + x;
            if (visited[idx]) continue;
            visited[idx] = 1;
            
            if (isEdge(idx)) continue;
            
            const pixelIdx = idx * 4;
            const colorDiff = Math.abs(originalData[pixelIdx] - startColor[0]) +
                             Math.abs(originalData[pixelIdx + 1] - startColor[1]) +
                             Math.abs(originalData[pixelIdx + 2] - startColor[2]);
            
            if (colorDiff > toleranceValue) continue;
            
            maskData[pixelIdx] = 255;
            maskData[pixelIdx + 1] = 255;
            maskData[pixelIdx + 2] = 255;
            maskData[pixelIdx + 3] = 255;
            pixelCount++;
            
            // Add neighbors
            if (x + 1 < width) stack.push({x: x + 1, y});
            if (x - 1 >= 0) stack.push({x: x - 1, y});
            if (y + 1 < height) stack.push({x, y: y + 1});
            if (y - 1 >= 0) stack.push({x, y: y - 1});
            
            // Update UI in batches to improve performance
            batch++;
            if (batch >= batchSize) {
                batch = 0;
                // Allow the UI to update
                requestAnimationFrame(() => {});
            }
        }
        
        // Update the canvas immediately for visual feedback
        const currentCtx = getContext(currentCanvasRef, 'current');
        if (currentCtx && cachedMask) {
            // Draw the updated mask directly
            requestAnimationFrame(() => {
                currentCtx.clearRect(0, 0, width, height);
                
                // Draw faded background
                if (originalCanvasRef.current) {
                    currentCtx.globalAlpha = 0.3;
                    currentCtx.drawImage(originalCanvasRef.current, 0, 0);
                    currentCtx.globalAlpha = 1;
                }
                
                // Draw the mask with layer color
                const tempCanvas = document.createElement('canvas');
                tempCanvas.width = width;
                tempCanvas.height = height;
                const tempCtx = tempCanvas.getContext('2d');
                tempCtx.putImageData(cachedMask, 0, 0);
                
                currentCtx.globalCompositeOperation = 'source-over';
                currentCtx.fillStyle = layer.color;
                currentCtx.globalAlpha = 0.7;
                
                // Create colored version
                for (let i = 0; i < maskData.length; i += 4) {
                    if (maskData[i + 3] > 0) {
                        const pixelIndex = i / 4;
                        const x = pixelIndex % width;
                        const y = Math.floor(pixelIndex / width);
                        currentCtx.fillRect(x, y, 1, 1);
                    }
                }
            });
        }
        
        // Queue the state update
        canvasWorkRef.current.pendingUpdates.push({
            layerId: layer.id,
            changes: {
                mask: cachedMask || new ImageData(maskData, width, height),
                pixelCount: layer.pixelCount + pixelCount
            }
        });
        
        // Defer the React state update
        if (canvasWorkRef.current.updateTimer) {
            clearTimeout(canvasWorkRef.current.updateTimer);
        }
        
        canvasWorkRef.current.updateTimer = setTimeout(() => {
            canvasWorkRef.current.isProcessing = false;
            flushPendingUpdates();
            saveLayerState(layer.id);
        }, 16); // ~60fps
    };
    
    const magicWandFloodFill = (startX, startY, fromEdgeCanvas = false) => {
        const layer = layers[currentLayerIndex];
        const width = originalImage.width;
        const height = originalImage.height;
        
        // Mark as processing
        canvasWorkRef.current.isProcessing = true;
        
        const visited = new Uint8Array(width * height);
        const stack = [];
        
        // Use brush size to define initial selection area in radius mode
        if (magicWandMode === 'radius') {
            // Add all pixels within brush radius to initial stack
            for (let dy = -brushSize; dy <= brushSize; dy++) {
                for (let dx = -brushSize; dx <= brushSize; dx++) {
                    const dist = Math.sqrt(dx * dx + dy * dy);
                    if (dist <= brushSize) {
                        const px = startX + dx;
                        const py = startY + dy;
                        if (px >= 0 && px < width && py >= 0 && py < height) {
                            stack.push({x: px, y: py});
                        }
                    }
                }
            }
        } else {
            // Original behavior - single point
            stack.push({x: startX, y: startY});
        }
        
        // Use cached data if available
        const originalData = cachedImageDataRef.current ? cachedImageDataRef.current.data :
            getContext(originalCanvasRef, 'original').getImageData(0, 0, width, height).data;
        
        // Work directly on cached mask
        let maskData;
        const cachedMask = canvasWorkRef.current.maskCache.get(layer.id);
        if (cachedMask) {
            maskData = cachedMask.data;
        } else {
            const newMask = new ImageData(layer.mask.data.slice(), width, height);
            maskData = newMask.data;
            canvasWorkRef.current.maskCache.set(layer.id, newMask);
        }
        
        const startIdx = (startY * width + startX) * 4;
        const startColor = [originalData[startIdx], originalData[startIdx + 1], originalData[startIdx + 2]];
        const startBrightness = (startColor[0] + startColor[1] + startColor[2]) / 3;
        
        let pixelCount = 0;
        
        while (stack.length > 0) {
            const {x, y} = stack.pop();
            
            if (x < 0 || x >= width || y < 0 || y >= height) continue;
            
            const idx = y * width + x;
            if (visited[idx]) continue;
            visited[idx] = 1;
            
            const pixelIdx = idx * 4;
            const pixelColor = [originalData[pixelIdx], originalData[pixelIdx + 1], originalData[pixelIdx + 2]];
            const pixelBrightness = (pixelColor[0] + pixelColor[1] + pixelColor[2]) / 3;
            
            const colorDiff = Math.abs(pixelColor[0] - startColor[0]) +
                             Math.abs(pixelColor[1] - startColor[1]) +
                             Math.abs(pixelColor[2] - startColor[2]);
            const brightnessDiff = Math.abs(pixelBrightness - startBrightness);
            
            if (colorDiff + brightnessDiff > tolerance * 4) continue;
            
            maskData[pixelIdx] = 255;
            maskData[pixelIdx + 1] = 255;
            maskData[pixelIdx + 2] = 255;
            maskData[pixelIdx + 3] = 255;
            pixelCount++;
            
            for (let dy = -1; dy <= 1; dy++) {
                for (let dx = -1; dx <= 1; dx++) {
                    if (dx === 0 && dy === 0) continue;
                    stack.push({x: x + dx, y: y + dy});
                }
            }
        }
        
        // Queue the update instead of immediate state change
        canvasWorkRef.current.pendingUpdates.push({
            layerId: layer.id,
            changes: {
                mask: cachedMask || new ImageData(maskData, width, height),
                pixelCount: layer.pixelCount + pixelCount
            }
        });
        
        // Update canvas immediately for feedback
        requestAnimationFrame(() => {
            updateCurrentCanvas();
        });
        
        // Defer state update
        if (canvasWorkRef.current.updateTimer) {
            clearTimeout(canvasWorkRef.current.updateTimer);
        }
        
        canvasWorkRef.current.updateTimer = setTimeout(() => {
            canvasWorkRef.current.isProcessing = false;
            flushPendingUpdates();
            saveLayerState(layer.id);
        }, 16);
    };
    
    const despeckleLayer = () => {
        if (currentLayerIndex < 0 || !layers[currentLayerIndex]) {
            setStatus('No layer selected');
            return;
        }
        
        const layer = layers[currentLayerIndex];
        const width = originalImage.width;
        const height = originalImage.height;
        const thresholdSize = tolerance; // Use tolerance slider for maximum speckle size
        
        // Mark as processing
        canvasWorkRef.current.isProcessing = true;
        setStatus('Finding speckles...');
        
        // Work on a copy of the mask
        const maskData = layer.mask.data.slice();
        
        // First, find the bounding box of painted pixels
        let minX = width, minY = height, maxX = 0, maxY = 0;
        let hasPaintedPixels = false;
        
        for (let y = 0; y < height; y++) {
            for (let x = 0; x < width; x++) {
                const pixelIdx = (y * width + x) * 4;
                if (maskData[pixelIdx + 3] > 0) {
                    hasPaintedPixels = true;
                    minX = Math.min(minX, x);
                    minY = Math.min(minY, y);
                    maxX = Math.max(maxX, x);
                    maxY = Math.max(maxY, y);
                }
            }
        }
        
        if (!hasPaintedPixels) {
            setStatus('No painted areas found');
            canvasWorkRef.current.isProcessing = false;
            return;
        }
        
        // Store original boundaries before padding
        const originalMinX = minX;
        const originalMinY = minY;
        const originalMaxX = maxX;
        const originalMaxY = maxY;
        
        // Add padding to ensure we catch holes at edges
        minX = Math.max(0, minX - 1);
        minY = Math.max(0, minY - 1);
        maxX = Math.min(width - 1, maxX + 1);
        maxY = Math.min(height - 1, maxY + 1);
        
        const visited = new Uint8Array(width * height);
        let specklesFilled = 0;
        let totalPixelsFilled = 0;
        
        // Helper function to check if a hole is completely surrounded by painted pixels
        const isHoleSurrounded = (pixels) => {
            // More lenient margin - holes must be at least 1 pixel inside the boundary
            const margin = 1;
            for (const {x, y} of pixels) {
                if (x <= originalMinX + margin || x >= originalMaxX - margin || 
                    y <= originalMinY + margin || y >= originalMaxY - margin) {
                    return false;
                }
            }
            
            // Count painted neighbors for edge pixels of the hole only
            const edgePixels = new Set();
            for (const {x, y} of pixels) {
                // Check if this pixel is on the edge of the hole
                const neighbors = [
                    {x: x + 1, y}, {x: x - 1, y},
                    {x, y: y + 1}, {x, y: y - 1}
                ];
                
                for (const {x: nx, y: ny} of neighbors) {
                    if (nx >= 0 && nx < width && ny >= 0 && ny < height) {
                        const nIdx = (ny * width + nx) * 4;
                        if (maskData[nIdx + 3] > 0) {
                            // This pixel touches a painted pixel, so it's an edge
                            edgePixels.add(`${x},${y}`);
                            break;
                        }
                    }
                }
            }
            
            // If at least 25% of the hole pixels are edge pixels touching painted areas, it's likely a hole
            return edgePixels.size >= pixels.length * 0.25;
        };
        
        // Find all unpainted regions within the bounding box
        for (let y = minY; y <= maxY; y++) {
            for (let x = minX; x <= maxX; x++) {
                const idx = y * width + x;
                const pixelIdx = idx * 4;
                
                // Skip if already visited or already painted
                if (visited[idx] || maskData[pixelIdx + 3] > 0) continue;
                
                // Found an unpainted pixel - flood fill to find the region size
                const regionPixels = [];
                const stack = [{x, y}];
                let regionSize = 0;
                
                // Allow larger regions - multiply threshold by 10 for more aggressive filling
                while (stack.length > 0 && regionSize < thresholdSize * 10 + 1) {
                    const {x: cx, y: cy} = stack.pop();
                    
                    if (cx < 0 || cx >= width || cy < 0 || cy >= height) continue;
                    
                    const currentIdx = cy * width + cx;
                    if (visited[currentIdx]) continue;
                    
                    const currentPixelIdx = currentIdx * 4;
                    if (maskData[currentPixelIdx + 3] > 0) continue;
                    
                    visited[currentIdx] = 1;
                    regionPixels.push({x: cx, y: cy});
                    regionSize++;
                    
                    // Add neighbors
                    stack.push({x: cx + 1, y: cy});
                    stack.push({x: cx - 1, y: cy});
                    stack.push({x: cx, y: cy + 1});
                    stack.push({x: cx, y: cy - 1});
                }
                
                // If region is small enough and doesn't touch boundary, fill it
                // Allow up to 10x the threshold size for more aggressive filling
                if (regionSize <= thresholdSize * 10 && regionSize > 0 && isHoleSurrounded(regionPixels)) {
                    regionPixels.forEach(({x: px, y: py}) => {
                        const pIdx = (py * width + px) * 4;
                        maskData[pIdx] = 255;
                        maskData[pIdx + 1] = 255;
                        maskData[pIdx + 2] = 255;
                        maskData[pIdx + 3] = 255;
                    });
                    specklesFilled++;
                    totalPixelsFilled += regionSize;
                }
            }
        }
        
        // Update the layer mask
        const newMask = new ImageData(maskData, width, height);
        canvasWorkRef.current.maskCache.set(layer.id, newMask);
        
        // Update the canvas immediately for visual feedback
        requestAnimationFrame(() => {
            updateCurrentCanvas();
        });
        
        // Queue the state update
        canvasWorkRef.current.pendingUpdates.push({
            layerId: layer.id,
            changes: {
                mask: newMask,
                pixelCount: layer.pixelCount + totalPixelsFilled
            }
        });
        
        // Defer the React state update
        if (canvasWorkRef.current.updateTimer) {
            clearTimeout(canvasWorkRef.current.updateTimer);
        }
        
        canvasWorkRef.current.updateTimer = setTimeout(() => {
            canvasWorkRef.current.isProcessing = false;
            flushPendingUpdates();
            saveLayerState(layer.id);
            setStatus(`Filled ${specklesFilled} speckles`);
        }, 16);
    };
    
    // Initialize brush canvas when image loads
    const initBrushCanvas = useCallback((img) => {
        const imageToUse = img || originalImage;
        if (!imageToUse) return;
        
        brushCanvasRef.current = document.createElement('canvas');
        brushCanvasRef.current.width = imageToUse.width;
        brushCanvasRef.current.height = imageToUse.height;
        brushCtxRef.current = brushCanvasRef.current.getContext('2d', { willReadFrequently: true });
        brushCtxRef.current.lineCap = 'round';
        brushCtxRef.current.lineJoin = 'round';
    }, [originalImage]);

    // Update dirty rectangle
    const updateDirtyRect = (x, y, radius) => {
        const bounds = {
            left: Math.max(0, Math.floor(x - radius)),
            top: Math.max(0, Math.floor(y - radius)),
            right: Math.min(originalImage.width, Math.ceil(x + radius)),
            bottom: Math.min(originalImage.height, Math.ceil(y + radius))
        };
        
        if (!dirtyRectRef.current) {
            dirtyRectRef.current = bounds;
        } else {
            dirtyRectRef.current.left = Math.min(dirtyRectRef.current.left, bounds.left);
            dirtyRectRef.current.top = Math.min(dirtyRectRef.current.top, bounds.top);
            dirtyRectRef.current.right = Math.max(dirtyRectRef.current.right, bounds.right);
            dirtyRectRef.current.bottom = Math.max(dirtyRectRef.current.bottom, bounds.bottom);
        }
    };

    // Optimized brush drawing with interpolation
    const drawBrush = (x, y) => {
        if (currentLayerIndex < 0 || !brushCtxRef.current) return;
        
        const width = originalImage.width;
        const height = originalImage.height;
        
        // Ensure coordinates are within bounds
        if (x < 0 || x >= width || y < 0 || y >= height) return;
        
        const ctx = brushCtxRef.current;
        
        // Set composite operation
        ctx.globalCompositeOperation = currentTool === 'eraser' ? 'destination-out' : 'source-over';
        
        if (lastBrushPosRef.current && 
            (Math.abs(x - lastBrushPosRef.current.x) > 1 || 
             Math.abs(y - lastBrushPosRef.current.y) > 1)) {
            // Draw interpolated line
            ctx.beginPath();
            ctx.moveTo(lastBrushPosRef.current.x, lastBrushPosRef.current.y);
            ctx.lineTo(x, y);
            ctx.lineWidth = brushSize * 2;
            
            if (brushMode === 'spray') {
                // Create spray effect with gradient
                const gradient = ctx.createRadialGradient(x, y, 0, x, y, brushSize);
                gradient.addColorStop(0, 'rgba(255, 255, 255, 1)');
                gradient.addColorStop(0.5, 'rgba(255, 255, 255, 0.5)');
                gradient.addColorStop(1, 'rgba(255, 255, 255, 0)');
                ctx.strokeStyle = gradient;
            } else {
                ctx.strokeStyle = 'white';
            }
            
            ctx.stroke();
            
            // Update dirty rect for the line
            updateDirtyRect(lastBrushPosRef.current.x, lastBrushPosRef.current.y, brushSize);
            updateDirtyRect(x, y, brushSize);
        } else {
            // Draw single dot
            ctx.beginPath();
            
            if (brushShape === 'circle') {
                ctx.arc(x, y, brushSize, 0, Math.PI * 2);
            } else {
                ctx.rect(x - brushSize, y - brushSize, brushSize * 2, brushSize * 2);
            }
            
            if (brushMode === 'spray') {
                const gradient = ctx.createRadialGradient(x, y, 0, x, y, brushSize);
                gradient.addColorStop(0, 'rgba(255, 255, 255, 1)');
                gradient.addColorStop(0.5, 'rgba(255, 255, 255, 0.5)');
                gradient.addColorStop(1, 'rgba(255, 255, 255, 0)');
                ctx.fillStyle = gradient;
            } else {
                ctx.fillStyle = 'white';
            }
            
            ctx.fill();
            updateDirtyRect(x, y, brushSize);
        }
        
        lastBrushPosRef.current = { x, y };
        
        // Schedule update
        if (brushUpdateTimerRef.current) {
            clearTimeout(brushUpdateTimerRef.current);
        }
        
        brushUpdateTimerRef.current = setTimeout(() => {
            flushBrushToMask();
        }, 16); // 60fps
    };
    
    // Apply brush canvas to mask
    const flushBrushToMask = () => {
        if (!dirtyRectRef.current || currentLayerIndex < 0) return;
        
        const layer = layers[currentLayerIndex];
        const rect = dirtyRectRef.current;
        const width = rect.right - rect.left;
        const height = rect.bottom - rect.top;
        
        if (width <= 0 || height <= 0) return;
        
        // Get brush data from dirty region
        const brushData = brushCtxRef.current.getImageData(rect.left, rect.top, width, height);
        
        // Get or create cached mask
        let cachedMask = canvasWorkRef.current.maskCache.get(layer.id);
        if (!cachedMask) {
            cachedMask = new ImageData(layer.mask.data.slice(), originalImage.width, originalImage.height);
            canvasWorkRef.current.maskCache.set(layer.id, cachedMask);
        }
        
        // Apply brush data to mask
        const maskData = cachedMask.data;
        const brushPixels = brushData.data;
        
        for (let y = 0; y < height; y++) {
            for (let x = 0; x < width; x++) {
                const brushIdx = (y * width + x) * 4;
                const maskIdx = ((rect.top + y) * originalImage.width + (rect.left + x)) * 4;
                
                if (currentTool === 'eraser') {
                    // Eraser: reduce alpha
                    const alpha = brushPixels[brushIdx + 3] / 255;
                    maskData[maskIdx + 3] = Math.max(0, maskData[maskIdx + 3] * (1 - alpha));
                } else {
                    // Brush: increase alpha
                    const alpha = brushPixels[brushIdx + 3];
                    maskData[maskIdx] = 255;
                    maskData[maskIdx + 1] = 255;
                    maskData[maskIdx + 2] = 255;
                    maskData[maskIdx + 3] = Math.min(255, maskData[maskIdx + 3] + alpha);
                }
            }
        }
        
        // Update the layer with new mask
        canvasWorkRef.current.pendingUpdates.push({
            layerId: layer.id,
            changes: {
                mask: cachedMask,
                pixelCount: countMaskPixels(cachedMask)
            }
        });
        
        // Clear dirty rect and flush updates
        dirtyRectRef.current = null;
        flushPendingUpdates();
        
        // Update canvas display
        requestAnimationFrame(() => {
            updateCurrentCanvas();
        });
    };
    
    const drawBezier = (points) => {
        const layer = layers[currentLayerIndex];
        const width = originalImage.width;
        const height = originalImage.height;
        
        const tempCanvas = document.createElement('canvas');
        tempCanvas.width = width;
        tempCanvas.height = height;
        const tempCtx = tempCanvas.getContext('2d', { willReadFrequently: true });
        
        tempCtx.strokeStyle = 'white';
        tempCtx.lineWidth = brushSize;
        tempCtx.lineCap = 'round';
        
        tempCtx.beginPath();
        tempCtx.moveTo(points[0].x, points[0].y);
        tempCtx.bezierCurveTo(
            points[1].x, points[1].y,
            points[2].x, points[2].y,
            points[3].x, points[3].y
        );
        tempCtx.stroke();
        
        const tempData = tempCtx.getImageData(0, 0, width, height).data;
        const newMask = new ImageData(layer.mask.data.slice(), width, height);
        const maskData = newMask.data;
        
        let pixelCount = 0;
        for (let i = 0; i < tempData.length; i += 4) {
            if (tempData[i + 3] > 0) {
                maskData[i] = 255;
                maskData[i + 1] = 255;
                maskData[i + 2] = 255;
                maskData[i + 3] = 255;
                pixelCount++;
            }
        }
        
        const newLayers = [...layers];
        newLayers[currentLayerIndex].mask = newMask;
        newLayers[currentLayerIndex].pixelCount += pixelCount;
        setLayers(newLayers);
        saveLayerState(layer.id);
    };
    
    const undo = useCallback(() => {
        if (currentLayerIndex < 0) return;
        
        const layer = layers[currentLayerIndex];
        const history = layerHistoryRef.current.get(layer.id);
        
        if (!history || history.currentIndex < 0 || history.states.length === 0) return;
        
        // Special case: if we're at index 0, we're going back to empty state
        if (history.currentIndex === 0) {
            // Create an empty mask
            const emptyMask = new ImageData(layer.mask.width, layer.mask.height);
            const newLayers = [...layers];
            newLayers[currentLayerIndex].mask = emptyMask;
            newLayers[currentLayerIndex].pixelCount = 0;
            
            // Update the mask cache to empty
            canvasWorkRef.current.maskCache.set(layer.id, emptyMask);
            
            history.currentIndex = -1;
            setLayers(newLayers);
            setStatus('Undo - Cleared');
            return;
        }
        
        history.currentIndex--;
        const newLayers = [...layers];
        const restoredMask = new ImageData(
            history.states[history.currentIndex].data.slice(),
            history.states[history.currentIndex].width,
            history.states[history.currentIndex].height
        );
        newLayers[currentLayerIndex].mask = restoredMask;
        
        // Update the mask cache to match the restored state
        canvasWorkRef.current.maskCache.set(layer.id, restoredMask);
        
        let pixelCount = 0;
        for (let i = 3; i < newLayers[currentLayerIndex].mask.data.length; i += 4) {
            if (newLayers[currentLayerIndex].mask.data[i] > 128) pixelCount++;
        }
        newLayers[currentLayerIndex].pixelCount = pixelCount;
        
        setLayers(newLayers);
        setStatus('Undo');
    }, [currentLayerIndex, layers]);
    
    const redo = useCallback(() => {
        if (currentLayerIndex < 0) return;
        
        const layer = layers[currentLayerIndex];
        const history = layerHistoryRef.current.get(layer.id);
        
        if (!history) return;
        
        // Check if we can redo
        if (history.currentIndex >= history.states.length - 1) return;
        
        // Special case: if we're at -1, we're redoing from empty state
        if (history.currentIndex === -1 && history.states.length > 0) {
            history.currentIndex = 0;
        } else {
            history.currentIndex++;
        }
        
        const newLayers = [...layers];
        const restoredMask = new ImageData(
            history.states[history.currentIndex].data.slice(),
            history.states[history.currentIndex].width,
            history.states[history.currentIndex].height
        );
        newLayers[currentLayerIndex].mask = restoredMask;
        
        // Update the mask cache to match the restored state
        canvasWorkRef.current.maskCache.set(layer.id, restoredMask);
        
        let pixelCount = 0;
        for (let i = 3; i < newLayers[currentLayerIndex].mask.data.length; i += 4) {
            if (newLayers[currentLayerIndex].mask.data[i] > 128) pixelCount++;
        }
        newLayers[currentLayerIndex].pixelCount = pixelCount;
        
        setLayers(newLayers);
        setStatus('Redo');
    }, [currentLayerIndex, layers]);
    
    // Keep layersRef in sync with layers state
    useEffect(() => {
        layersRef.current = layers;
    }, [layers]);
    
    // No longer need to update canvases when fullscreen mode changes
    // since we're using CSS display:none instead of conditional rendering
    
    useEffect(() => {
        const handleKeyDown = (e) => {
            if (e.ctrlKey && e.key === 'z') {
                e.preventDefault();
                undo();
            } else if (e.ctrlKey && e.key === 'y') {
                e.preventDefault();
                redo();
            } else if (e.key === 'F11') {
                e.preventDefault();
                if (currentLayerIndex >= 0) {
                    setIsFullscreenMode(prev => !prev);
                }
            } else if (selection && currentTool === 'selection') {
                // Selection tool keyboard shortcuts
                if (e.ctrlKey || e.metaKey) {
                    switch(e.key.toLowerCase()) {
                        case 'x':
                            e.preventDefault();
                            cutSelection();
                            break;
                        case 'c':
                            e.preventDefault();
                            copySelection();
                            break;
                        case 'v':
                            e.preventDefault();
                            pasteSelection();
                            break;
                        default:
                            break;
                    }
                } else if (e.key === 'Delete' || e.key === 'Backspace') {
                    e.preventDefault();
                    deleteSelection();
                }
            }
        };
        
        const handleMessage = (event) => {
            try {
                if (event.data.type === 'updateTransform') {
                    const currentLayers = layersRef.current;
                    const newLayers = [...currentLayers];
                    if (newLayers[event.data.layerIndex]) {
                        newLayers[event.data.layerIndex].transform = event.data.transform;
                        setLayers(newLayers);
                    }
                } else if (event.data.type === 'updateBaseTransform') {
                    setBaseTransform(event.data.transform);
                } else if (event.data.type === 'updateLayerMask') {
                    const { layerIndex, maskData, width, height } = event.data;
                    const currentLayers = layersRef.current;
                    if (layerIndex >= 0 && layerIndex < currentLayers.length && 
                        width === originalImage.width && height === originalImage.height) {
                        const updatedLayers = [...currentLayers];
                        updatedLayers[layerIndex] = {
                            ...updatedLayers[layerIndex],
                            mask: new Uint8Array(maskData)
                        };
                        setLayers(updatedLayers);
                        canvasWorkRef.current.maskCache.set(updatedLayers[layerIndex].id, new Uint8Array(maskData));
                        setStatus(`Updated ${updatedLayers[layerIndex].name} from editor`);
                    }
                }
            } catch (error) {
                console.error('Error handling message:', error);
                setStatus('Error updating layer from editor');
            }
        };
        
        document.addEventListener('keydown', handleKeyDown);
        window.addEventListener('message', handleMessage);
        
        return () => {
            document.removeEventListener('keydown', handleKeyDown);
            window.removeEventListener('message', handleMessage);
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [undo, redo, selection, currentTool, cutSelection, copySelection, pasteSelection, deleteSelection, originalImage, currentLayerIndex]);
    
    // Cleanup projection windows on unmount
    useEffect(() => {
        return () => {
            // Close all projection windows on component unmount
            projectionWindowsRef.current.forEach(window => {
                if (window && !window.closed) {
                    window.close();
                }
            });
            projectionWindowsRef.current.clear();
        };
    }, []);
    
    // Re-initialize brush canvas when originalImage changes
    useEffect(() => {
        if (originalImage && !brushCtxRef.current) {
            initBrushCanvas(originalImage);
        }
    }, [originalImage, initBrushCanvas]);
    
    const renameLayer = (index, newName) => {
        const newLayers = [...layers];
        newLayers[index].name = newName || `Layer ${index + 1}`;
        setLayers(newLayers);
    };
    
    const copyLayer = (index) => {
        const original = layers[index];
        const copy = {
            id: Date.now(),
            name: original.name + ' copy',
            color: original.color,
            mask: new ImageData(original.mask.data.slice(), original.mask.width, original.mask.height),
            visible: true,
            pixelCount: original.pixelCount,
            transform: { ...original.transform }
        };
        
        setLayers([...layers, copy]);
        layerHistoryRef.current.set(copy.id, { states: [], currentIndex: -1 });
        
        setStatus(`Copied ${original.name}`);
    };
    
    // K-means clustering for auto-layer detection
    const kMeansClustering = (pixels, k, maxIterations = 20) => {
        // Initialize centroids with k-means++ method
        const centroids = [];
        centroids.push(pixels[Math.floor(Math.random() * pixels.length)]);
        
        for (let i = 1; i < k; i++) {
            const distances = pixels.map(pixel => {
                let minDist = Infinity;
                centroids.forEach(centroid => {
                    const dist = Math.sqrt(
                        Math.pow(pixel[0] - centroid[0], 2) +
                        Math.pow(pixel[1] - centroid[1], 2) +
                        Math.pow(pixel[2] - centroid[2], 2)
                    );
                    minDist = Math.min(minDist, dist);
                });
                return minDist;
            });
            
            const sum = distances.reduce((a, b) => a + b, 0);
            let rand = Math.random() * sum;
            for (let j = 0; j < distances.length; j++) {
                rand -= distances[j];
                if (rand <= 0) {
                    centroids.push(pixels[j]);
                    break;
                }
            }
        }
        
        // Assign pixels to clusters
        let assignments = new Array(pixels.length);
        
        for (let iter = 0; iter < maxIterations; iter++) {
            // Assign each pixel to nearest centroid
            let changed = false;
            for (let i = 0; i < pixels.length; i++) {
                let minDist = Infinity;
                let bestCluster = 0;
                
                for (let j = 0; j < k; j++) {
                    const dist = Math.sqrt(
                        Math.pow(pixels[i][0] - centroids[j][0], 2) +
                        Math.pow(pixels[i][1] - centroids[j][1], 2) +
                        Math.pow(pixels[i][2] - centroids[j][2], 2)
                    );
                    
                    if (dist < minDist) {
                        minDist = dist;
                        bestCluster = j;
                    }
                }
                
                if (assignments[i] !== bestCluster) {
                    changed = true;
                    assignments[i] = bestCluster;
                }
            }
            
            if (!changed) break;
            
            // Update centroids
            const sums = Array(k).fill(null).map(() => [0, 0, 0, 0]);
            for (let i = 0; i < pixels.length; i++) {
                const cluster = assignments[i];
                sums[cluster][0] += pixels[i][0];
                sums[cluster][1] += pixels[i][1];
                sums[cluster][2] += pixels[i][2];
                sums[cluster][3]++;
            }
            
            for (let i = 0; i < k; i++) {
                if (sums[i][3] > 0) {
                    centroids[i] = [
                        sums[i][0] / sums[i][3],
                        sums[i][1] / sums[i][3],
                        sums[i][2] / sums[i][3]
                    ];
                }
            }
        }
        
        return { centroids, assignments };
    };
    
    // Find connected components for each cluster
    const findConnectedComponents = (assignments, width, height, minSize = 100) => {
        const visited = new Uint8Array(width * height);
        const components = [];
        
        // Find max cluster number without spreading array
        let maxCluster = 0;
        for (let i = 0; i < assignments.length; i++) {
            if (assignments[i] > maxCluster) maxCluster = assignments[i];
        }
        
        for (let cluster = 0; cluster <= maxCluster; cluster++) {
            for (let i = 0; i < assignments.length; i++) {
                if (assignments[i] === cluster && !visited[i]) {
                    const component = [];
                    const stack = [i];
                    
                    while (stack.length > 0) {
                        const idx = stack.pop();
                        if (visited[idx]) continue;
                        
                        visited[idx] = 1;
                        component.push(idx);
                        
                        const x = idx % width;
                        const y = Math.floor(idx / width);
                        
                        // Check 4-connected neighbors
                        const neighbors = [
                            { x: x - 1, y },
                            { x: x + 1, y },
                            { x, y: y - 1 },
                            { x, y: y + 1 }
                        ];
                        
                        for (const neighbor of neighbors) {
                            if (neighbor.x >= 0 && neighbor.x < width && 
                                neighbor.y >= 0 && neighbor.y < height) {
                                const nIdx = neighbor.y * width + neighbor.x;
                                if (assignments[nIdx] === cluster && !visited[nIdx]) {
                                    stack.push(nIdx);
                                }
                            }
                        }
                    }
                    
                    if (component.length >= minSize) {
                        components.push({ cluster, pixels: component });
                    }
                }
            }
        }
        
        return components;
    };
    
    const autoCreateLayers = async () => {
        if (!originalImage) {
            setStatus('Please upload an image first');
            return;
        }
        
        setIsProcessingAutoLayers(true);
        setProcessingProgress(0);
        setProcessingStep('Starting...');
        
        try {
            const ctx = getContext(originalCanvasRef, 'original');
            const imageData = ctx.getImageData(0, 0, originalImage.width, originalImage.height);
            const data = imageData.data;
            
            // Give UI time to update
            await new Promise(resolve => setTimeout(resolve, 10));
            
            // Sample pixels for k-means (every 4th pixel for speed)
            setProcessingStep('Sampling pixels...');
            setProcessingProgress(10);
            const sampledPixels = [];
            for (let i = 0; i < data.length; i += 16) {
                sampledPixels.push([data[i], data[i + 1], data[i + 2]]);
            }
            
            await new Promise(resolve => setTimeout(resolve, 10));
            
            setProcessingStep('Finding color clusters...');
            setProcessingProgress(20);
            
            // Run k-means clustering
            const { centroids } = kMeansClustering(sampledPixels, autoLayerCount);
            
            await new Promise(resolve => setTimeout(resolve, 10));
            
            // Map all pixels to clusters in chunks to prevent freezing
            setProcessingStep('Assigning pixels to clusters...');
            const fullAssignments = new Array(originalImage.width * originalImage.height);
            const chunkSize = 10000;
            
            for (let chunk = 0; chunk < fullAssignments.length; chunk += chunkSize) {
                const endChunk = Math.min(chunk + chunkSize, fullAssignments.length);
                
                for (let i = chunk; i < endChunk; i++) {
                    const pixelIdx = i * 4;
                    let minDist = Infinity;
                    let bestCluster = 0;
                    
                    for (let j = 0; j < centroids.length; j++) {
                        const dist = Math.sqrt(
                            Math.pow(data[pixelIdx] - centroids[j][0], 2) +
                            Math.pow(data[pixelIdx + 1] - centroids[j][1], 2) +
                            Math.pow(data[pixelIdx + 2] - centroids[j][2], 2)
                        );
                        
                        if (dist < minDist) {
                            minDist = dist;
                            bestCluster = j;
                        }
                    }
                    
                    fullAssignments[i] = bestCluster;
                }
                
                // Update progress
                const progress = 20 + (chunk / fullAssignments.length) * 40;
                setProcessingProgress(Math.round(progress));
                
                // Give UI time to update
                await new Promise(resolve => setTimeout(resolve, 1));
            }
            
            setProcessingStep('Finding connected regions...');
            setProcessingProgress(65);
            await new Promise(resolve => setTimeout(resolve, 10));
            
            // Find connected components
            const components = findConnectedComponents(
                fullAssignments, 
                originalImage.width, 
                originalImage.height,
                (originalImage.width * originalImage.height) / 100 // Min 1% of image
            );
            
            // Sort components by size
            components.sort((a, b) => b.pixels.length - a.pixels.length);
            
            setProcessingStep('Creating layers...');
            setProcessingProgress(70);
            await new Promise(resolve => setTimeout(resolve, 10));
            
            // Clear existing layers
            setLayers([]);
            layerHistoryRef.current.clear();
            canvasWorkRef.current.maskCache.clear();
            
            // Create layers for each significant component
            const newLayers = [];
            const usedColors = new Set();
            
            // Limit to user's requested number of layers
            const maxLayers = Math.min(autoLayerCount, components.length, 10);
            
            for (let index = 0; index < maxLayers; index++) {
                const component = components[index];
                
                const layerId = Date.now() + index;
                
                // Generate unique color
                let color;
                do {
                    color = getRandomColor();
                } while (usedColors.has(color));
                usedColors.add(color);
                
                // Create mask for this component in chunks
                const mask = new ImageData(originalImage.width, originalImage.height);
                const maskData = mask.data;
                
                // Process pixels in chunks to prevent blocking
                const pixelChunkSize = 50000;
                for (let i = 0; i < component.pixels.length; i += pixelChunkSize) {
                    const end = Math.min(i + pixelChunkSize, component.pixels.length);
                    
                    for (let j = i; j < end; j++) {
                        const idx = component.pixels[j];
                        const pixelIdx = idx * 4;
                        maskData[pixelIdx] = 255;
                        maskData[pixelIdx + 1] = 255;
                        maskData[pixelIdx + 2] = 255;
                        maskData[pixelIdx + 3] = 255;
                    }
                    
                    // Update progress more granularly
                    if (i % (pixelChunkSize * 2) === 0) {
                        const componentProgress = i / component.pixels.length;
                        const overallProgress = 70 + (index / maxLayers) * 25 + 
                                              (componentProgress * 25 / maxLayers);
                        setProcessingProgress(Math.round(overallProgress));
                        setProcessingStep(`Creating layer ${index + 1} of ${maxLayers}...`);
                        await new Promise(resolve => setTimeout(resolve, 1));
                    }
                }
                
                // Determine layer name based on position (sample subset for speed)
                const sampleSize = Math.min(1000, component.pixels.length);
                const sampleStep = Math.floor(component.pixels.length / sampleSize);
                let sumX = 0, sumY = 0;
                
                for (let i = 0; i < component.pixels.length; i += sampleStep) {
                    const idx = component.pixels[i];
                    sumX += idx % originalImage.width;
                    sumY += Math.floor(idx / originalImage.width);
                }
                
                const sampledCount = Math.ceil(component.pixels.length / sampleStep);
                const avgX = sumX / sampledCount;
                const avgY = sumY / sampledCount;
                
                let name = 'Region ' + (index + 1);
                if (avgY < originalImage.height * 0.3) name = 'Top ' + name;
                else if (avgY > originalImage.height * 0.7) name = 'Bottom ' + name;
                if (avgX < originalImage.width * 0.3) name = 'Left ' + name;
                else if (avgX > originalImage.width * 0.7) name = 'Right ' + name;
                
                const newLayer = {
                    id: layerId,
                    name,
                    color,
                    mask,
                    visible: true,
                    pixelCount: component.pixels.length,
                    transform: { x: 0, y: 0, scale: 1, rotation: 0 }
                };
                
                newLayers.push(newLayer);
                layerHistoryRef.current.set(layerId, { states: [], currentIndex: -1 });
                canvasWorkRef.current.maskCache.set(layerId, mask);
                
                // Update progress
                const progress = 70 + (index / maxLayers) * 25;
                setProcessingProgress(Math.round(progress));
                await new Promise(resolve => setTimeout(resolve, 10));
            }
            
            setLayers(newLayers);
            setCurrentLayerIndex(0);
            
            setProcessingProgress(100);
            setProcessingStep('Complete!');
            setStatus(`Created ${newLayers.length} layers automatically`);
            
        } catch (error) {
            console.error('Auto-layer error:', error);
            setStatus('Error creating layers');
        } finally {
            setTimeout(() => {
                setIsProcessingAutoLayers(false);
                setProcessingProgress(0);
                setProcessingStep('');
            }, 1000);
        }
    };
    
    return (
        <div className="projection-mapping-container">
            <div className="tools-panel">
                <h3>Image Upload</h3>
                <input type="file" id="imageUpload" accept="image/*" onChange={handleImageUpload} />
                
                <h3>Base Transform (All Layers)</h3>
                <div className="control-group" style={{ backgroundColor: '#2a2a2a', padding: '15px', borderRadius: '8px', marginBottom: '20px' }}>
                    
                    {/* Transform Mode Toggle */}
                    <div style={{ marginBottom: '15px' }}>
                        <label style={{ display: 'block', marginBottom: '5px' }}>Transform Mode:</label>
                        <div style={{ display: 'flex', gap: '10px' }}>
                            <button 
                                onClick={() => setBaseTransform({...baseTransform, mode: 'basic'})}
                                style={{ 
                                    padding: '5px 15px', 
                                    backgroundColor: baseTransform.mode === 'basic' ? '#4CAF50' : '#444',
                                    color: 'white',
                                    border: 'none',
                                    borderRadius: '4px',
                                    cursor: 'pointer'
                                }}
                            >
                                Basic
                            </button>
                            <button 
                                onClick={() => setBaseTransform({...baseTransform, mode: 'corners'})}
                                style={{ 
                                    padding: '5px 15px', 
                                    backgroundColor: baseTransform.mode === 'corners' ? '#4CAF50' : '#444',
                                    color: 'white',
                                    border: 'none',
                                    borderRadius: '4px',
                                    cursor: 'pointer'
                                }}
                            >
                                Corner Alignment
                            </button>
                        </div>
                    </div>

                    {/* Basic Transform Controls */}
                    {baseTransform.mode === 'basic' && (
                        <>
                            <label>Position X: <span>{baseTransform.x}</span></label>
                            <input 
                                type="range" 
                                min="-1000" 
                                max="1000" 
                                value={baseTransform.x}
                                onChange={(e) => setBaseTransform({...baseTransform, x: parseInt(e.target.value)})}
                            />
                            
                            <label>Position Y: <span>{baseTransform.y}</span></label>
                            <input 
                                type="range" 
                                min="-1000" 
                                max="1000" 
                                value={baseTransform.y}
                                onChange={(e) => setBaseTransform({...baseTransform, y: parseInt(e.target.value)})}
                            />
                            
                            <label>Scale: <span>{baseTransform.scale.toFixed(1)}</span></label>
                            <input 
                                type="range" 
                                min="0.1" 
                                max="10" 
                                step="0.01"
                                value={baseTransform.scale}
                                onChange={(e) => setBaseTransform({...baseTransform, scale: parseFloat(e.target.value)})}
                            />
                            
                            <label>Rotation: <span>{baseTransform.rotation}°</span></label>
                            <input 
                                type="range" 
                                min="-180" 
                                max="180" 
                                step="0.1"
                                value={baseTransform.rotation}
                                onChange={(e) => setBaseTransform({...baseTransform, rotation: parseFloat(e.target.value)})}
                            />
                        </>
                    )}

                    {/* Corner-Based Transform Controls */}
                    {baseTransform.mode === 'corners' && (
                        <>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                            {/* Top Left */}
                            <div style={{ padding: '10px', backgroundColor: '#333', borderRadius: '4px' }}>
                                <label style={{ fontSize: '12px', color: '#ccc' }}>Top Left</label>
                                <div>
                                    <input 
                                        type="number" 
                                        placeholder="X"
                                        value={baseTransform.corners.topLeft.x}
                                        onChange={(e) => setBaseTransform({
                                            ...baseTransform,
                                            corners: {
                                                ...baseTransform.corners,
                                                topLeft: { ...baseTransform.corners.topLeft, x: parseInt(e.target.value) || 0 }
                                            }
                                        })}
                                        style={{ width: '100%', marginBottom: '5px', padding: '2px' }}
                                    />
                                    <input 
                                        type="number" 
                                        placeholder="Y"
                                        value={baseTransform.corners.topLeft.y}
                                        onChange={(e) => setBaseTransform({
                                            ...baseTransform,
                                            corners: {
                                                ...baseTransform.corners,
                                                topLeft: { ...baseTransform.corners.topLeft, y: parseInt(e.target.value) || 0 }
                                            }
                                        })}
                                        style={{ width: '100%', padding: '2px' }}
                                    />
                                </div>
                            </div>

                            {/* Top Right */}
                            <div style={{ padding: '10px', backgroundColor: '#333', borderRadius: '4px' }}>
                                <label style={{ fontSize: '12px', color: '#ccc' }}>Top Right</label>
                                <div>
                                    <input 
                                        type="number" 
                                        placeholder="X"
                                        value={baseTransform.corners.topRight.x}
                                        onChange={(e) => setBaseTransform({
                                            ...baseTransform,
                                            corners: {
                                                ...baseTransform.corners,
                                                topRight: { ...baseTransform.corners.topRight, x: parseInt(e.target.value) || 0 }
                                            }
                                        })}
                                        style={{ width: '100%', marginBottom: '5px', padding: '2px' }}
                                    />
                                    <input 
                                        type="number" 
                                        placeholder="Y"
                                        value={baseTransform.corners.topRight.y}
                                        onChange={(e) => setBaseTransform({
                                            ...baseTransform,
                                            corners: {
                                                ...baseTransform.corners,
                                                topRight: { ...baseTransform.corners.topRight, y: parseInt(e.target.value) || 0 }
                                            }
                                        })}
                                        style={{ width: '100%', padding: '2px' }}
                                    />
                                </div>
                            </div>

                            {/* Bottom Left */}
                            <div style={{ padding: '10px', backgroundColor: '#333', borderRadius: '4px' }}>
                                <label style={{ fontSize: '12px', color: '#ccc' }}>Bottom Left</label>
                                <div>
                                    <input 
                                        type="number" 
                                        placeholder="X"
                                        value={baseTransform.corners.bottomLeft.x}
                                        onChange={(e) => setBaseTransform({
                                            ...baseTransform,
                                            corners: {
                                                ...baseTransform.corners,
                                                bottomLeft: { ...baseTransform.corners.bottomLeft, x: parseInt(e.target.value) || 0 }
                                            }
                                        })}
                                        style={{ width: '100%', marginBottom: '5px', padding: '2px' }}
                                    />
                                    <input 
                                        type="number" 
                                        placeholder="Y"
                                        value={baseTransform.corners.bottomLeft.y}
                                        onChange={(e) => setBaseTransform({
                                            ...baseTransform,
                                            corners: {
                                                ...baseTransform.corners,
                                                bottomLeft: { ...baseTransform.corners.bottomLeft, y: parseInt(e.target.value) || 0 }
                                            }
                                        })}
                                        style={{ width: '100%', padding: '2px' }}
                                    />
                                </div>
                            </div>

                            {/* Bottom Right */}
                            <div style={{ padding: '10px', backgroundColor: '#333', borderRadius: '4px' }}>
                                <label style={{ fontSize: '12px', color: '#ccc' }}>Bottom Right</label>
                                <div>
                                    <input 
                                        type="number" 
                                        placeholder="X"
                                        value={baseTransform.corners.bottomRight.x}
                                        onChange={(e) => setBaseTransform({
                                            ...baseTransform,
                                            corners: {
                                                ...baseTransform.corners,
                                                bottomRight: { ...baseTransform.corners.bottomRight, x: parseInt(e.target.value) || 0 }
                                            }
                                        })}
                                        style={{ width: '100%', marginBottom: '5px', padding: '2px' }}
                                    />
                                    <input 
                                        type="number" 
                                        placeholder="Y"
                                        value={baseTransform.corners.bottomRight.y}
                                        onChange={(e) => setBaseTransform({
                                            ...baseTransform,
                                            corners: {
                                                ...baseTransform.corners,
                                                bottomRight: { ...baseTransform.corners.bottomRight, y: parseInt(e.target.value) || 0 }
                                            }
                                        })}
                                        style={{ width: '100%', padding: '2px' }}
                                    />
                                </div>
                            </div>
                        </div>
                        
                        {/* Corner Alignment Presets */}
                        <div style={{ marginTop: '15px' }}>
                            <label style={{ fontSize: '12px', color: '#ccc', marginBottom: '8px', display: 'block' }}>Alignment Presets:</label>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '5px', marginBottom: '10px' }}>
                                <button 
                                    onClick={() => setBaseTransform({
                                        ...baseTransform,
                                        corners: {
                                            topLeft: { x: 0, y: 0 },
                                            topRight: { x: originalImage?.width || 1000, y: 0 },
                                            bottomLeft: { x: 0, y: originalImage?.height || 600 },
                                            bottomRight: { x: originalImage?.width || 1000, y: originalImage?.height || 600 }
                                        }
                                    })}
                                    style={{ 
                                        padding: '4px 8px', 
                                        fontSize: '11px',
                                        backgroundColor: '#555',
                                        color: 'white',
                                        border: 'none',
                                        borderRadius: '3px',
                                        cursor: 'pointer'
                                    }}
                                >
                                    Reset Corners
                                </button>
                                <button 
                                    onClick={() => setBaseTransform({
                                        ...baseTransform,
                                        corners: {
                                            topLeft: { x: 100, y: 100 },
                                            topRight: { x: (originalImage?.width || 1000) - 100, y: 100 },
                                            bottomLeft: { x: 100, y: (originalImage?.height || 600) - 100 },
                                            bottomRight: { x: (originalImage?.width || 1000) - 100, y: (originalImage?.height || 600) - 100 }
                                        }
                                    })}
                                    style={{ 
                                        padding: '4px 8px', 
                                        fontSize: '11px',
                                        backgroundColor: '#555',
                                        color: 'white',
                                        border: 'none',
                                        borderRadius: '3px',
                                        cursor: 'pointer'
                                    }}
                                >
                                    Inset 100px
                                </button>
                                <button 
                                    onClick={() => setBaseTransform({
                                        ...baseTransform,
                                        corners: {
                                            topLeft: { x: -50, y: 0 },
                                            topRight: { x: (originalImage?.width || 1000) + 50, y: 0 },
                                            bottomLeft: { x: 0, y: originalImage?.height || 600 },
                                            bottomRight: { x: originalImage?.width || 1000, y: originalImage?.height || 600 }
                                        }
                                    })}
                                    style={{ 
                                        padding: '4px 8px', 
                                        fontSize: '11px',
                                        backgroundColor: '#555',
                                        color: 'white',
                                        border: 'none',
                                        borderRadius: '3px',
                                        cursor: 'pointer'
                                    }}
                                >
                                    Keystone Top
                                </button>
                                <button 
                                    onClick={() => setBaseTransform({
                                        ...baseTransform,
                                        corners: {
                                            topLeft: { x: 0, y: 0 },
                                            topRight: { x: originalImage?.width || 1000, y: 0 },
                                            bottomLeft: { x: -50, y: originalImage?.height || 600 },
                                            bottomRight: { x: (originalImage?.width || 1000) + 50, y: originalImage?.height || 600 }
                                        }
                                    })}
                                    style={{ 
                                        padding: '4px 8px', 
                                        fontSize: '11px',
                                        backgroundColor: '#555',
                                        color: 'white',
                                        border: 'none',
                                        borderRadius: '3px',
                                        cursor: 'pointer'
                                    }}
                                >
                                    Keystone Bottom
                                </button>
                            </div>
                        </div>
                        </>
                    )}
                    
                    <div style={{ display: 'flex', gap: '10px', marginTop: '15px' }}>
                        <button onClick={openBaseTransformWindow} style={{ flex: 1 }}>📺 Preview</button>
                        <button onClick={resetBaseTransform} style={{ flex: 1 }}>Reset</button>
                    </div>
                </div>
                
                <h3>Edge Detection</h3>
                <div className="control-group">
                    <label>Sensitivity: <span>{edgeSensitivity}</span></label>
                    <input 
                        type="range" 
                        min="5" 
                        max="500" 
                        value={edgeSensitivity}
                        onChange={(e) => setEdgeSensitivity(parseInt(e.target.value))}
                        disabled={edgeProcessing}
                    />
                    <input
                        type="number"
                        min="1"
                        max="2000"
                        value={edgeSensitivity}
                        onChange={(e) => {
                            const val = parseInt(e.target.value) || 5;
                            setEdgeSensitivity(Math.max(1, Math.min(2000, val)));
                        }}
                        style={{ width: '60px', marginLeft: '10px' }}
                        disabled={edgeProcessing}
                    />
                    {edgeProcessing && <small style={{display: 'block', marginTop: '5px'}}>Processing edges...</small>}
                </div>
                
                <h3>Tools</h3>
                {currentTool === 'selection' && selection && selection.data && (
                    <div style={{ 
                        backgroundColor: '#2a2a2a', 
                        padding: '10px', 
                        marginBottom: '10px',
                        borderRadius: '4px',
                        fontSize: '12px'
                    }}>
                        <strong>Selection Active:</strong> {selection.width}×{selection.height}px
                        <div style={{ marginTop: '5px' }}>
                            <button onClick={cutSelection} style={{ marginRight: '5px', padding: '4px 8px', fontSize: '12px' }}>
                                Cut (Ctrl+X)
                            </button>
                            <button onClick={copySelection} style={{ marginRight: '5px', padding: '4px 8px', fontSize: '12px' }}>
                                Copy (Ctrl+C)
                            </button>
                            <button onClick={deleteSelection} style={{ padding: '4px 8px', fontSize: '12px' }}>
                                Delete
                            </button>
                            {clipboard && (
                                <button onClick={pasteSelection} style={{ marginLeft: '10px', padding: '4px 8px', fontSize: '12px' }}>
                                    Paste ({clipboard.width}×{clipboard.height})
                                </button>
                            )}
                        </div>
                    </div>
                )}
                <div className="tool-buttons">
                    <button 
                        className={`tool-button ${currentTool === 'select' ? 'active' : ''}`}
                        onClick={() => { setCurrentTool('select'); setBezierPoints([]); setSelection(null); }}
                    >
                        ⬚ Select
                    </button>
                    <button 
                        className={`tool-button ${currentTool === 'floodFill' ? 'active' : ''}`}
                        onClick={() => { setCurrentTool('floodFill'); setBezierPoints([]); }}
                    >
                        🪣 Fill
                    </button>
                    <button 
                        className={`tool-button ${currentTool === 'magicWand' ? 'active' : ''}`}
                        onClick={() => { setCurrentTool('magicWand'); setBezierPoints([]); }}
                    >
                        ✨ Magic
                    </button>
                    <button 
                        className={`tool-button ${currentTool === 'brush' ? 'active' : ''}`}
                        onClick={() => { setCurrentTool('brush'); setBezierPoints([]); }}
                    >
                        🖌️ Brush
                    </button>
                    <button 
                        className={`tool-button ${currentTool === 'eraser' ? 'active' : ''}`}
                        onClick={() => { setCurrentTool('eraser'); setBezierPoints([]); }}
                    >
                        🗑️ Eraser
                    </button>
                    <button 
                        className={`tool-button ${currentTool === 'bezier' ? 'active' : ''}`}
                        onClick={() => { setCurrentTool('bezier'); setBezierPoints([]); }}
                    >
                        📐 Bezier
                    </button>
                    <button 
                        className={`tool-button ${currentTool === 'despeckle' ? 'active' : ''}`}
                        onClick={() => { setCurrentTool('despeckle'); setBezierPoints([]); }}
                    >
                        ✨ Despeckle
                    </button>
                </div>
                
                <div className="control-group">
                    <label>{currentTool === 'despeckle' ? 'Speckle Size' : 'Tolerance'}: <span>{tolerance}</span></label>
                    <input 
                        type="range" 
                        min="5" 
                        max="500" 
                        value={tolerance}
                        onChange={(e) => setTolerance(parseInt(e.target.value))}
                    />
                    <input
                        type="number"
                        min="1"
                        max="2000"
                        value={tolerance}
                        onChange={(e) => {
                            const val = parseInt(e.target.value) || 5;
                            setTolerance(Math.max(1, Math.min(2000, val)));
                        }}
                        style={{ width: '60px', marginLeft: '10px' }}
                    />
                    
                    <label>Brush Size: <span>{brushSize}</span></label>
                    <input 
                        type="range" 
                        min="1" 
                        max="500" 
                        value={brushSize}
                        onChange={(e) => setBrushSize(parseInt(e.target.value))}
                    />
                    <input
                        type="number"
                        min="1"
                        max="2000"
                        value={brushSize}
                        onChange={(e) => {
                            const val = parseInt(e.target.value) || 1;
                            setBrushSize(Math.max(1, Math.min(2000, val)));
                        }}
                        style={{ width: '60px', marginLeft: '10px' }}
                    />
                    
                    <label>Brush Mode:</label>
                    <div style={{ display: 'flex', gap: '5px', marginBottom: '10px' }}>
                        <button 
                            className={`tool-button ${brushMode === 'solid' ? 'active' : ''}`}
                            onClick={() => setBrushMode('solid')}
                            style={{ flex: 1 }}
                        >
                            Solid
                        </button>
                        <button 
                            className={`tool-button ${brushMode === 'spray' ? 'active' : ''}`}
                            onClick={() => setBrushMode('spray')}
                            style={{ flex: 1 }}
                        >
                            Spray
                        </button>
                    </div>
                    
                    <label>Brush Shape:</label>
                    <div style={{ display: 'flex', gap: '5px', marginBottom: '10px' }}>
                        <button 
                            className={`tool-button ${brushShape === 'circle' ? 'active' : ''}`}
                            onClick={() => setBrushShape('circle')}
                            style={{ flex: 1 }}
                        >
                            ⭕ Circle
                        </button>
                        <button 
                            className={`tool-button ${brushShape === 'square' ? 'active' : ''}`}
                            onClick={() => setBrushShape('square')}
                            style={{ flex: 1 }}
                        >
                            ⬜ Square
                        </button>
                    </div>
                </div>
                
                <h3>Layers</h3>
                <div style={{ fontSize: '12px', color: '#888', marginBottom: '5px' }}>
                    Ctrl/Cmd+Click to select multiple layers
                </div>
                <button onClick={createNewLayer}>+ New Layer</button>
                <button onClick={downloadAllLayers}>⬇ Download All</button>
                <button onClick={() => document.getElementById('layerImport').click()}>📁 Import Layers</button>
                {selectedLayers.size >= 2 && (
                    <button onClick={flattenSelectedLayers} style={{ backgroundColor: '#4CAF50' }}>
                        🔀 Flatten {selectedLayers.size} Layers
                    </button>
                )}
                <input 
                    type="file" 
                    id="layerImport" 
                    accept="image/*" 
                    multiple 
                    style={{ display: 'none' }}
                    onChange={handleLayerImport}
                />
                
                <div className="control-group">
                    <label>Auto Create Layers: <span>{autoLayerCount}</span></label>
                    <input 
                        type="range" 
                        min="3" 
                        max="10" 
                        value={autoLayerCount}
                        onChange={(e) => setAutoLayerCount(parseInt(e.target.value))}
                        disabled={isProcessingAutoLayers}
                    />
                    <button 
                        onClick={autoCreateLayers}
                        disabled={isProcessingAutoLayers || !originalImage}
                        style={{ width: '100%', marginTop: '10px' }}
                    >
                        {isProcessingAutoLayers ? 'Processing...' : '🎨 Auto Create Layers'}
                    </button>
                    {isProcessingAutoLayers && (
                        <div style={{ marginTop: '10px' }}>
                            <div style={{ 
                                width: '100%', 
                                height: '20px', 
                                backgroundColor: '#2a2a2a', 
                                borderRadius: '10px',
                                overflow: 'hidden'
                            }}>
                                <div style={{ 
                                    width: `${processingProgress}%`, 
                                    height: '100%', 
                                    backgroundColor: '#4CAF50',
                                    transition: 'width 0.3s ease'
                                }} />
                            </div>
                            <small style={{ display: 'block', marginTop: '5px', textAlign: 'center' }}>
                                {processingStep}
                            </small>
                        </div>
                    )}
                </div>
                
                <div className="layers-list">
                    {layers.map((layer, index) => {
                        const coverage = ((layer.pixelCount / (originalImage?.width * originalImage?.height || 1)) * 100).toFixed(1);
                        const isSelected = selectedLayers.has(layer.id);
                        
                        return (
                            <div 
                                key={layer.id} 
                                className={`layer-item ${index === currentLayerIndex ? 'active' : ''} ${isSelected ? 'selected' : ''}`}
                                onClick={(e) => {
                                    if (e.ctrlKey || e.metaKey) {
                                        // Toggle selection with Ctrl/Cmd click
                                        const newSelection = new Set(selectedLayers);
                                        if (isSelected) {
                                            newSelection.delete(layer.id);
                                        } else {
                                            newSelection.add(layer.id);
                                        }
                                        setSelectedLayers(newSelection);
                                    } else if (!e.target.closest('button') && !e.target.closest('[contenteditable]')) {
                                        // Normal click - select only this layer
                                        selectLayer(index);
                                        setSelectedLayers(new Set());
                                    }
                                }}
                            >
                                <div>
                                    <span 
                                        className="color-square" 
                                        style={{ backgroundColor: layer.color }}
                                        onClick={() => toggleLayerVisibility(index)}
                                    ></span>
                                    <span 
                                        contentEditable
                                        suppressContentEditableWarning
                                        onBlur={(e) => renameLayer(index, e.target.textContent)}
                                        title="Click to edit layer name"
                                    >
                                        {layer.name}
                                    </span>
                                    <small style={{ float: 'right' }}>
                                        {layer.pixelCount} px ({coverage}%)
                                    </small>
                                </div>
                                <div className="layer-controls">
                                    <button onClick={() => selectLayer(index)} title="Select for editing">Edit</button>
                                    <button onClick={() => copyLayer(index)} title="Copy layer">Copy</button>
                                    <button onClick={() => { selectLayer(index); setIsFullscreenMode(true); }} title="Edit in fullscreen">Focus</button>
                                    <button onClick={() => openFullscreenEditor(index)} title="Open layer editor window">Editor</button>
                                    <button onClick={() => openProjectionWindow(index)} title="Projection window">Project</button>
                                    <button onClick={() => deleteLayer(index)} title="Delete layer">Delete</button>
                                    <select 
                                        onChange={(e) => {
                                            const action = e.target.value;
                                            e.target.value = ''; // Reset select
                                            switch(action) {
                                                case 'download': downloadLayer(index, 'none'); break;
                                                case 'download-layer': downloadLayer(index, 'layer'); break;
                                                case 'download-combined': downloadLayer(index, 'combined'); break;
                                                default: break;
                                            }
                                        }}
                                        title="More actions"
                                        style={{ marginLeft: 'auto' }}
                                    >
                                        <option value="">⋯</option>
                                        <option value="download">Download Original</option>
                                        <option value="download-layer">Download w/ Layer Transform</option>
                                        <option value="download-combined">Download w/ All Transforms</option>
                                    </select>
                                </div>
                            </div>
                        );
                    })}
                </div>
                
                <div className="shortcut-info">
                    <h4>Keyboard Shortcuts:</h4>
                    Ctrl+Z: Undo<br />
                    Ctrl+Y: Redo<br />
                    <br />
                    <h4>Projection Window:</h4>
                    Arrow Keys: Move<br />
                    Shift+Arrow: Move fast<br />
                    +/-: Scale<br />
                    [/]: Rotate<br />
                    R: Reset<br />
                    C: Center<br />
                    H: Hide controls<br />
                    F11: Fullscreen
                </div>
            </div>
            
            <div className={`canvas-area ${isFullscreenMode ? 'fullscreen-mode' : ''}`}>
                <div className="canvas-container" style={{ display: isFullscreenMode ? 'none' : 'flex' }}>
                    <div className="canvas-label">Original</div>
                    <canvas ref={originalCanvasRef}></canvas>
                </div>
                <div className="canvas-container" style={{ display: isFullscreenMode ? 'none' : 'flex' }}>
                    <div className="canvas-label">Edge Detection</div>
                    <canvas 
                        ref={edgeCanvasRef}
                        style={{ cursor: getCursorStyle() }}
                        onMouseDown={handleCanvasMouseDown}
                        onMouseMove={handleCanvasMouseMove}
                        onMouseUp={handleCanvasMouseUp}
                        onMouseLeave={handleCanvasMouseLeave}
                    ></canvas>
                    {cursorPosition.visible && (currentTool === 'brush' || currentTool === 'eraser') && cursorPosition.activeCanvas === edgeCanvasRef.current && (
                        <div 
                            className="cursor-preview"
                            style={{
                                left: cursorPosition.x - brushSize,
                                top: cursorPosition.y - brushSize,
                                width: brushSize * 2,
                                height: brushSize * 2,
                                borderRadius: brushShape === 'circle' ? '50%' : '0',
                                borderColor: currentTool === 'eraser' ? '#ff4444' : layers[currentLayerIndex]?.color || '#fff'
                            }}
                        />
                    )}
                </div>
                <div className="canvas-container" style={{ display: isFullscreenMode ? 'none' : 'flex' }}>
                    <div className="canvas-label">All Layers Combined</div>
                    <canvas ref={combinedCanvasRef}></canvas>
                </div>
                <div className={`canvas-container ${isFullscreenMode ? 'fullscreen-canvas' : ''}`}>
                    <div className="canvas-label">
                        Current Layer: <span>{layers[currentLayerIndex]?.name || 'None'}</span>
                        {currentLayerIndex >= 0 && (
                            <button 
                                className="fullscreen-toggle"
                                onClick={() => setIsFullscreenMode(!isFullscreenMode)}
                                title={isFullscreenMode ? "Exit fullscreen" : "Enter fullscreen"}
                            >
                                {isFullscreenMode ? '⊞' : '⊡'}
                            </button>
                        )}
                        {isFullscreenMode && (
                            <div style={{ display: 'inline-flex', alignItems: 'center', marginLeft: '20px', gap: '10px' }}>
                                <button 
                                    onClick={() => setCanvasZoom(Math.max(0.1, canvasZoom - 0.1))}
                                    style={{ padding: '2px 8px', fontSize: '14px' }}
                                >
                                    -
                                </button>
                                <span style={{ minWidth: '60px', textAlign: 'center' }}>
                                    {Math.round(canvasZoom * 100)}%
                                </span>
                                <input 
                                    type="range"
                                    min="0.1"
                                    max="5"
                                    step="0.1"
                                    value={canvasZoom}
                                    onChange={(e) => setCanvasZoom(parseFloat(e.target.value))}
                                    style={{ width: '150px' }}
                                />
                                <button 
                                    onClick={() => setCanvasZoom(Math.min(5, canvasZoom + 0.1))}
                                    style={{ padding: '2px 8px', fontSize: '14px' }}
                                >
                                    +
                                </button>
                                <button 
                                    onClick={() => setCanvasZoom(1)}
                                    style={{ padding: '2px 8px', fontSize: '14px' }}
                                >
                                    Reset
                                </button>
                            </div>
                        )}
                    </div>
                    <canvas 
                        ref={currentCanvasRef}
                        style={{ cursor: getCursorStyle() }}
                        onMouseDown={handleCanvasMouseDown}
                        onMouseMove={handleCanvasMouseMove}
                        onMouseUp={handleCanvasMouseUp}
                        onMouseLeave={handleCanvasMouseLeave}
                    ></canvas>
                    {cursorPosition.visible && (currentTool === 'brush' || currentTool === 'eraser') && cursorPosition.activeCanvas === currentCanvasRef.current && (
                        <div 
                            className="cursor-preview"
                            style={{
                                left: cursorPosition.x - brushSize,
                                top: cursorPosition.y - brushSize,
                                width: brushSize * 2,
                                height: brushSize * 2,
                                borderRadius: brushShape === 'circle' ? '50%' : '0',
                                borderColor: currentTool === 'eraser' ? '#ff4444' : layers[currentLayerIndex]?.color || '#fff'
                            }}
                        />
                    )}
                </div>
            </div>
            
            {status && <div className="status show">{status}</div>}
        </div>
    );
}

export default ProjectionMapping;
