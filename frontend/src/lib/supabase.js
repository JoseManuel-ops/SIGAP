import { createClient } from "@supabase/supabase-js";

const url = (import.meta.env.VITE_SUPABASE_URL ?? "").trim().replace(/\/+$/, "");
const llaveAnon = (import.meta.env.VITE_SUPABASE_ANON_KEY ?? "").trim();

// Sin variables, createClient lanza un error y la página queda en blanco.
// Se deja en null para que App muestre un mensaje claro.
export const supabase = url && llaveAnon ? createClient(url, llaveAnon) : null;
