"""
高德地图工具模块

提供高德地图 Web API 接口封装：
- 地理编码：地址转经纬度
- 逆地理编码：经纬度转地址
- 天气查询：实时天气和预报天气
- POI 搜索：关键字搜索、周边搜索
"""

import os
import requests
from typing import Optional, List, Dict, Any


class AMapClient:
    """
    高德地图客户端
    
    使用环境变量 AMAP_MAPS_API_KEY 获取 API Key
    """
    
    BASE_URL = "https://restapi.amap.com"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        初始化高德地图客户端
        
        Args:
            api_key: 高德地图 API Key，默认从环境变量 AMAP_MAPS_API_KEY 获取
        """
        self.api_key = api_key or os.getenv("AMAP_MAPS_API_KEY")
        if not self.api_key:
            raise ValueError("请设置环境变量 AMAP_MAPS_API_KEY")
    
    def _request(self, url: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        发送 HTTP GET 请求
        
        Args:
            url: 请求 URL
            params: 请求参数
        
        Returns:
            响应 JSON 数据
        
        Raises:
            Exception: 请求失败或高德 API 返回错误
        """
        params["key"] = self.api_key
        params["output"] = "JSON"
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") != "1":
                raise Exception(f"高德 API 错误：{data.get('info', '未知错误')}")
            
            return data
        except requests.exceptions.Timeout:
            raise Exception("请求超时")
        except requests.exceptions.RequestException as e:
            raise Exception(f"网络请求失败：{e}")
    
    def geocode(self, address: str, city: Optional[str] = None) -> Dict[str, Any]:
        """
        地理编码：将结构化地址转换为经纬度坐标
        
        Args:
            address: 结构化地址（如：北京市朝阳区阜通东大街6号）
            city: 查询城市（可选，如：北京）
        
        Returns:
            {
                "location": "经度,纬度",
                "formatted_address": "结构化地址",
                "province": "省份",
                "city": "城市",
                "district": "区县",
                "street": "街道",
                "number": "门牌",
                "adcode": "区域编码"
            }
        """
        params = {
            "address": address,
        }
        if city:
            params["city"] = city
        
        url = f"{self.BASE_URL}/v3/geocode/geo"
        data = self._request(url, params)
        
        geocodes = data.get("geocodes", [])
        if not geocodes:
            raise Exception(f"未找到地址：{address}")
        
        result = geocodes[0]
        return {
            "location": result.get("location", ""),
            "formatted_address": result.get("formatted_address", ""),
            "province": result.get("province", ""),
            "city": result.get("city", ""),
            "district": result.get("district", ""),
            "street": result.get("street", ""),
            "number": result.get("number", ""),
            "adcode": result.get("adcode", ""),
        }
    
    def get_city_adcode(self, city_name: str) -> str:
        """
        获取城市 adcode
        
        Args:
            city_name: 城市名称（如：北京、北京市）
        
        Returns:
            str: 城市 adcode
        
        Raises:
            Exception: 未找到城市
        """
        # 先尝试使用地理编码 API 获取 adcode
        params = {
            "address": city_name,
            "city": city_name,
        }
        
        url = f"{self.BASE_URL}/v3/geocode/geo"
        data = self._request(url, params)
        
        geocodes = data.get("geocodes", [])
        if geocodes:
            adcode = geocodes[0].get("adcode", "")
            if adcode and len(adcode) >= 2:
                # 取前2位+4个0作为城市级adcode（如：110000）
                return adcode[:2] + "0000"
        
        # 如果地理编码失败，尝试使用 POI 搜索
        params = {
            "keywords": city_name,
            "types": "010000",
            "page": 1,
            "page_size": 5,
        }
        
        url = f"{self.BASE_URL}/v3/place/text"
        data = self._request(url, params)
        
        pois = data.get("pois", [])
        for poi in pois:
            cityname = poi.get("cityname", "")
            adcode = poi.get("adcode", "")
            if cityname and city_name.replace("市", "") in cityname.replace("市", ""):
                if adcode and len(adcode) >= 6:
                    return adcode[:6]
        
        raise Exception(f"未找到城市 adcode：{city_name}")
    
    def reverse_geocode(
        self,
        longitude: float,
        latitude: float,
        radius: int = 1000
    ) -> Dict[str, Any]:
        """
        逆地理编码：将经纬度转换为结构化地址
        
        Args:
            longitude: 经度
            latitude: 纬度
            radius: 搜索半径（米），默认 1000 米
        
        Returns:
            {
                "formatted_address": "结构化地址",
                "province": "省份",
                "city": "城市",
                "district": "区县",
                "township": "乡镇",
                "neighborhood": "小区",
                "building": "建筑物",
                "adcode": "区域编码",
                "pois": [...]  # 附近 POI 列表
            }
        """
        params = {
            "location": f"{longitude},{latitude}",
            "radius": radius,
            "extensions": "all",
        }
        
        url = f"{self.BASE_URL}/v3/geocode/regeo"
        data = self._request(url, params)
        
        regeocode = data.get("regeocode", {})
        address_component = regeocode.get("addressComponent", {})
        
        return {
            "formatted_address": regeocode.get("formattedAddress", ""),
            "province": address_component.get("province", ""),
            "city": address_component.get("city", ""),
            "district": address_component.get("district", ""),
            "township": address_component.get("township", ""),
            "neighborhood": address_component.get("neighborhood", {}).get("name", ""),
            "building": address_component.get("building", {}).get("name", ""),
            "adcode": address_component.get("adcode", ""),
            "pois": regeocode.get("pois", []),
        }
    
    def get_weather(
        self,
        city: str,
        extensions: str = "base"
    ) -> Dict[str, Any]:
        """
        天气查询：查询目标区域当前/未来的天气情况
        
        Args:
            city: 城市 adcode 或城市名称（如：110000 或 北京）
                如果传入城市名，将自动转换为 adcode。
            extensions: 气象类型
                - "base": 返回实况天气（默认）
                - "all": 返回预报天气
        
        Returns:
            实况天气 (extensions="base")：
            {
                "province": "省份",
                "city": "城市",
                "adcode": "区域编码",
                "weather": "天气现象",
                "temperature": "实时气温",
                "winddirection": "风向",
                "windpower": "风力级别",
                "humidity": "空气湿度",
                "reporttime": "数据发布时间"
            }
            
            预报天气 (extensions="all")：
            {
                "city": "城市名称",
                "adcode": "城市编码",
                "province": "省份名称",
                "reporttime": "预报发布时间",
                "casts": [
                    {
                        "date": "日期",
                        "week": "星期几",
                        "dayweather": "白天天气现象",
                        "nightweather": "晚上天气现象",
                        "daytemp": "白天温度",
                        "nighttemp": "晚上温度",
                        "daywind": "白天风向",
                        "nightwind": "晚上风向",
                        "daypower": "白天风力",
                        "nightpower": "晚上风力"
                    },
                    ...
                ]
            }
        """
        params = {
            "city": city,
            "extensions": extensions,
        }
        
        # 如果 city 不是纯数字（不是 adcode），自动转换为 adcode
        if not city.isdigit():
            try:
                city_adcode = self.get_city_adcode(city)
                params["city"] = city_adcode
            except Exception as e:
                raise Exception(f"无法解析城市名称 '{city}'：{e}")
        
        url = f"{self.BASE_URL}/v3/weather/weatherInfo"
        data = self._request(url, params)
        
        if extensions == "base":
            lives = data.get("lives", [])
            if not lives:
                raise Exception(f"未找到天气信息：{city}")
            
            result = lives[0]
            return {
                "province": result.get("province", ""),
                "city": result.get("city", ""),
                "adcode": result.get("adcode", ""),
                "weather": result.get("weather", ""),
                "temperature": result.get("temperature", ""),
                "winddirection": result.get("winddirection", ""),
                "windpower": result.get("windpower", ""),
                "humidity": result.get("humidity", ""),
                "reporttime": result.get("reporttime", ""),
            }
        else:
            forecasts = data.get("forecasts", [])
            if not forecasts:
                raise Exception(f"未找到天气信息：{city}")
            
            result = forecasts[0]
            casts = result.get("casts", [])
            return {
                "city": result.get("city", ""),
                "adcode": result.get("adcode", ""),
                "province": result.get("province", ""),
                "reporttime": result.get("reporttime", ""),
                "casts": casts,
            }
    
    def search_poi(
        self,
        keywords: str,
        city: Optional[str] = None,
        citylimit: bool = False,
        types: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        POI 关键字搜索
        
        Args:
            keywords: 搜索关键字（如：肯德基、朝阳公园）
            city: 查询城市（可选，支持 citycode 或 adcode）
            citylimit: 是否限制城市范围，默认 False
            types: POI 类型（可选，如：050101 表示加油站）
            page: 页码，默认 1
            page_size: 每页数量，默认 20，最大 25
        
        Returns:
            {
                "count": 总数,
                "pois": [
                    {
                        "id": "POI ID",
                        "name": "名称",
                        "type": "类型",
                        "address": "地址",
                        "location": "经度,纬度",
                        "tel": "电话",
                        "distance": "距离（米）",
                        ...
                    },
                    ...
                ]
            }
        """
        params = {
            "keywords": keywords,
            "page": page,
            "offset": min(page_size, 25),
        }
        if city:
            params["city"] = city
            params["citylimit"] = "true" if citylimit else "false"
        if types:
            params["types"] = types
        
        url = f"{self.BASE_URL}/v3/place/text"
        data = self._request(url, params)
        
        pois = data.get("pois", [])
        return {
            "count": int(data.get("count", 0)),
            "pois": pois,
        }
    
    def search_poi_around(
        self,
        keywords: str,
        longitude: float,
        latitude: float,
        radius: int = 3000,
        types: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        POI 周边搜索
        
        Args:
            keywords: 搜索关键字
            longitude: 中心点经度
            latitude: 中心点纬度
            radius: 搜索半径（米），默认 3000 米
            types: POI 类型（可选）
            page: 页码，默认 1
            page_size: 每页数量，默认 20，最大 25
        
        Returns:
            {
                "count": 总数,
                "pois": [...]
            }
        """
        params = {
            "keywords": keywords,
            "location": f"{longitude},{latitude}",
            "radius": radius,
            "page": page,
            "offset": min(page_size, 25),
        }
        if types:
            params["types"] = types
        
        url = f"{self.BASE_URL}/v3/place/around"
        data = self._request(url, params)
        
        pois = data.get("pois", [])
        return {
            "count": int(data.get("count", 0)),
            "pois": pois,
        }


def get_amap_client(api_key: Optional[str] = None) -> AMapClient:
    """
    便捷函数：获取高德地图客户端
    
    Args:
        api_key: 高德地图 API Key（可选，默认从环境变量获取）
    
    Returns:
        AMapClient: 高德地图客户端实例
    """
    return AMapClient(api_key)
