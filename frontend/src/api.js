import axios from "axios";

export const API_BASE =
  process.env.REACT_APP_API_BASE || "http://localhost:8000/api";

export const api = axios.create({
  baseURL: API_BASE,
  withCredentials: true,
});

export function errorMessage(error, fallback) {
  return error?.response?.data?.error || fallback;
}
