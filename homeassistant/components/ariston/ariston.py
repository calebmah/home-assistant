"""Python module for interacting with Ariston API."""
import logging

import aiohttp


class Ariston:
    """Class for interacting with Ariston API."""

    _LOGGER = logging.getLogger(__name__)

    def __init__(self, session: aiohttp.ClientSession, host: str) -> None:
        """Initialize."""
        self._session = session
        self._host = host
        self._token = None
        self._account = None
        self._username = ""
        self._password = ""

        self._default_params = {"appId": "com.remotethermo.velis"}
        self._post_headers = {"expect": "100-continue"}

    def _default_headers(self):
        return {"ar.authToken": self._token}

    def _default_post_headers(self):
        headers = {}
        headers.update(self._post_headers)
        if self._token:
            headers.update(self._default_headers())
        return headers

    async def _get(self, url, headers=None, params=None) -> aiohttp.ClientResponse:
        headers = headers if headers else self._default_headers()
        params = params if params else self._default_params
        async with self._session.get(
            url,
            headers=headers,
            params=params,
        ) as resp:
            resp_read = await resp.read()
            if resp.status in [200, 500]:
                self._LOGGER.debug(
                    "%s status code received: %s", resp.status, resp_read
                )
            else:
                self._LOGGER.warning(
                    "%s status code received: %s", resp.status, resp_read
                )
            if resp.status == 405:
                self._LOGGER.info("Reauthenticating...")
                await self.authenticate(self._username, self._password)
                resp = await self._get(url, headers, params)
            return resp

    async def _post(
        self, url, json, headers=None, params=None
    ) -> aiohttp.ClientResponse:
        headers = headers if headers else self._default_post_headers()
        params = params if params else self._default_params
        async with self._session.post(
            url,
            headers=headers,
            params=params,
            json=json,
        ) as resp:
            if resp.status == 200:
                self._LOGGER.debug("%s status code received", resp.status)
            else:
                self._LOGGER.warning("%s status code received", resp.status)
            if resp.status == 405:
                self._LOGGER.info("Reauthenticating...")
                await self.authenticate(self._username, self._password)
                resp = await self._post(url, json, headers, params)
            return resp

    async def authenticate(self, username: str, password: str) -> bool:
        """Authenticate with the host."""
        self._username = username
        self._password = password
        url = self._host + "/api/v2/accounts/login"
        login_data = {
            "usr": username,
            "pwd": password,
            "imp": False,
            "notTrack": True,
        }
        try:
            async with self._session.post(
                url,
                headers=self._default_post_headers(),
                params=self._default_params,
                json=login_data,
            ) as resp:
                if resp.status != 200:
                    self._LOGGER.warning(
                        "%s Unexpected reply during login: %s", self, resp.status
                    )
                    raise Exception("Login unexpected reply code")
                resp_json = await resp.json()
                self._token = resp_json.get("token")
                self._account = resp_json.get("act")
                self._LOGGER.info("%s Authentication success %s", self, resp_json)
                return True

        except aiohttp.ClientConnectorError as exception:
            self._LOGGER.warning("%s Authentication login error", self)
            raise Exception("Login request exception") from exception

    async def get_plants(self):
        """Get available plants."""
        url = self._host + "/api/v2/velis/plants"
        resp = await self._get(url)
        return await resp.json()

    async def get_plant_data(self, gw_val):
        """Get individual plant data."""
        url = self._host + "/api/v2/velis/medPlantData/" + gw_val
        resp = await self._get(url)
        available = resp.status == 200
        if available:
            response = await resp.json()
            response["available"] = available
            return response
        return {"available": available}

    async def set_temperature(self, gw_val, temperature, eco):
        """Set the temperature."""
        url = self._host + "/api/v2/velis/medPlantData/" + gw_val + "/temperature"
        data = {"eco": eco, "new": temperature, "old": 0.0}
        resp = await self._post(url, data)
        return resp

    async def switch(self, gw_val, on_or_off):
        """Switches the heater on or off."""
        url = self._host + "/api/v2/velis/medPlantData/" + gw_val + "/switch"
        resp = await self._post(url, on_or_off)
        return resp

    async def switch_eco(self, gw_val, on_or_off):
        """Switch the eco mode on or off."""
        url = self._host + "/api/v2/velis/medPlantData/" + gw_val + "/switchEco"
        resp = await self._post(url, on_or_off)
        return resp

    async def switch_schedule(self, gw_val, on_or_off):
        """Switch the schedule mode on or off."""
        url = self._host + "/api/v2/velis/medPlantData/" + gw_val + "/mode"
        if on_or_off:
            data = {"new": 5, "old": 1}
        else:
            data = {"new": 1, "old": 5}
        resp = await self._post(url, data)
        return resp
