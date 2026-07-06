/**
 * 高德地图集成模块
 * 管理地图初始化、标记点、路线规划
 */
const MapView = {
    map: null,
    markers: [],
    routes: [],       // 导航线
    userLocation: null, // 用户位置 {lng, lat}
    placeSearch: null,

    /**
     * 初始化地图（惰性初始化，首次需要时调用）
     */
    init(force) {
        var container = document.getElementById('mapContainer');
        if (!container) return;
        // 确保面板展开，容器有尺寸
        var panel = document.getElementById('mapPanel');
        if (panel) panel.classList.remove('collapsed');

        if (this.map) {
            // 已存在的地图，resize 确保尺寸正确
            if (force) {
                setTimeout(function() { this.map.resize(); }.bind(this), 200);
            }
            return;
        }

        this.map = new AMap.Map(container, {
            zoom: 5,
            center: [104.0, 35.0],
            viewMode: '2D',
            resizeEnable: true,
        });

        this.map.addControl(new AMap.ToolBar({ position: 'RT' }));
        this.map.addControl(new AMap.Scale({ position: 'LB' }));

        AMap.plugin('AMap.PlaceSearch', function() {
            this.placeSearch = new AMap.PlaceSearch({
                pageSize: 10, pageIndex: 1,
                citylimit: false, autoFitView: true,
            });
        }.bind(this));

        this.map.on('click', function() {
            this.map.clearInfoWindow();
        }.bind(this));
    },

    /**
     * 设置用户位置
     */
    setUserLocation(lng, lat) {
        this.userLocation = { lng: lng, lat: lat };
    },

    /**
     * 绘制用户位置到目标的导航线
     */
    drawRoutes(destinations) {
        this.clearRoutes();
        if (!this.userLocation || !destinations || !this.map) return;
        var from = [this.userLocation.lng, this.userLocation.lat];
        destinations.forEach(function(dest) {
            if (dest.longitude == null || dest.latitude == null) return;
            var to = [dest.longitude, dest.latitude];
            var line = new AMap.Polyline({
                path: [from, to],
                strokeColor: '#2E8B7B',
                strokeWeight: 3,
                strokeOpacity: 0.6,
                strokeStyle: 'dashed',
                showDir: true,
                zIndex: 50,
            });
            line.setMap(this.map);
            this.routes.push(line);
        }.bind(this));
        // 缩放包含用户位置和所有目标
        var allPoints = [from];
        destinations.forEach(function(d) {
            if (d.longitude != null && d.latitude != null) allPoints.push([d.longitude, d.latitude]);
        });
        if (allPoints.length > 1) {
            this.map.setFitView(allPoints, false, [80, 80, 80, 80]);
        }
    },

    /**
     * 清除所有导航线
     */
    clearRoutes() {
        this.routes.forEach(function(r) { r.setMap(null); });
        this.routes = [];
    },

    /**
     * 显示多个标记点（红色）+ 用户位置（蓝色）+ 导航线
     */
    showLocations(locations) {
        this.init();
        this.clearMarkers();
        this.clearRoutes();

        if (!locations || locations.length === 0) return;
        if (typeof AMap === 'undefined') return;

        var allPoints = [];
        var self = this;

        // 用户位置（蓝色标记）
        if (this.userLocation) {
            var userPos = [this.userLocation.lng, this.userLocation.lat];
            allPoints.push(userPos);
            var userMarker = new AMap.Marker({
                position: userPos,
                title: '我的位置',
                icon: new AMap.Icon({
                    size: new AMap.Size(24, 24),
                    image: 'https://webapi.amap.com/theme/v1.3/markers/n/mark_b.png',
                    imageSize: new AMap.Size(24, 24),
                }),
                label: { content: '📍 我的位置', direction: 'top' },
                zIndex: 200,
            });
            userMarker.setMap(this.map);
            this.markers.push(userMarker);
        }

        // 目的地（红色标记）+ 导航线
        locations.forEach(function(loc, index) {
            if (loc.longitude == null || loc.latitude == null) return;
            var pos = [loc.longitude, loc.latitude];
            allPoints.push(pos);

            var marker = new AMap.Marker({
                position: pos,
                title: loc.name,
                icon: new AMap.Icon({
                    size: new AMap.Size(24, 24),
                    image: 'https://webapi.amap.com/theme/v1.3/markers/n/mark_r.png',
                    imageSize: new AMap.Size(24, 24),
                }),
                label: { content: (index + 1) + '. ' + loc.name, direction: 'top' },
                zIndex: 100 - index,
            });
            marker.on('click', function() { self.showInfoWindow(loc, marker); });
            marker.setMap(self.map);
            self.markers.push(marker);

            // 从用户位置画线到目的地
            if (self.userLocation) {
                var line = new AMap.Polyline({
                    path: [[self.userLocation.lng, self.userLocation.lat], pos],
                    strokeColor: '#2E8B7B',
                    strokeWeight: 3,
                    strokeOpacity: 0.7,
                    strokeStyle: 'dashed',
                    showDir: true,
                    zIndex: 50,
                });
                line.setMap(self.map);
                self.routes.push(line);
            }
        });

        // 自动调整视野包含所有点
        try {
            if (allPoints.length === 1) {
                this.map.setCenter(allPoints[0]);
                this.map.setZoom(14);
            } else if (allPoints.length > 1) {
                this.map.setFitView(allPoints, false, [80, 80, 80, 80]);
            }
        } catch (e) {}

        document.getElementById('mapPanel')?.classList.remove('collapsed');
    },

    /**
     * 标记单个地点
     */
    markLocation(location) {
        this.showLocations([location]);
    },

    /**
     * 显示信息窗
     */
    showInfoWindow(location, marker) {
        let tagsHTML = '';
        if (location.tags) {
            const tags = typeof location.tags === 'string'
                ? JSON.parse(location.tags) : location.tags;
            tagsHTML = tags.map(t => `<span>${t}</span>`).join('');
        }

        const infoWindow = new AMap.InfoWindow({
            content: `
                <div class="amap-info-card">
                    <h4>${location.name}</h4>
                    <p>${location.description || '暂无描述'}</p>
                    ${tagsHTML ? `<div class="info-tags">${tagsHTML}</div>` : ''}
                    <div class="info-actions">
                        <button class="info-btn" onclick="MapView.navigateTo(${location.longitude}, ${location.latitude}, '${location.name}')">
                            🚗 导航到此
                        </button>
                        <button class="info-btn" onclick="MapView.searchNearby(${location.longitude}, ${location.latitude})">
                            🔍 搜索周边
                        </button>
                    </div>
                </div>
            `,
            offset: new AMap.Pixel(0, -30),
        });

        infoWindow.open(this.map, marker.getPosition());
    },

    /**
     * 路线规划（导航）
     */
    navigateTo(lng, lat, name) {
        this.init();
        AMap.plugin('AMap.Driving', () => {
            const driving = new AMap.Driving({
                map: this.map,
                panel: null,
            });

            // 使用高德导航 URL Scheme 跳转
            const url = `https://uri.amap.com/navigation?to=${lng},${lat},${encodeURIComponent(name)}&mode=car&callnative=1`;
            window.open(url, '_blank');
        });
    },

    /**
     * 搜索周边
     */
    searchNearby(lng, lat) {
        if (!this.placeSearch) {
            AMap.plugin('AMap.PlaceSearch', () => {
                this.placeSearch = new AMap.PlaceSearch({
                    pageSize: 10,
                    autoFitView: true,
                });
                this.placeSearch.searchNearBy('', [lng, lat], 5000);
            });
        } else {
            this.placeSearch.searchNearBy('', [lng, lat], 5000);
        }
    },

    /**
     * 规划驾车路线
     */
    async planDrivingRoute(origin, destination) {
        this.init();
        return new Promise((resolve) => {
            AMap.plugin('AMap.Driving', () => {
                const driving = new AMap.Driving({
                    map: this.map,
                    panel: null,
                });
                driving.search(
                    new AMap.LngLat(origin.longitude, origin.latitude),
                    new AMap.LngLat(destination.longitude, destination.latitude),
                    (status, result) => {
                        if (status === 'complete') {
                            resolve(result);
                        } else {
                            resolve(null);
                        }
                    }
                );
            });
        });
    },

    /**
     * 清除所有标记
     */
    clearMarkers() {
        if (this.map) {
            this.map.clearMap();
            this.markers = [];
            this.routes = [];
        }
    },
};
