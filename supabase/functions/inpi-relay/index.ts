// inpi-relay: consulta a busca pública de marcas do INPI a partir de São Paulo (sa-east-1).
// O INPI descarta conexões de IPs fora do Brasil; o app (Streamlit Cloud, EUA) chama esta função
// com o cabeçalho x-region: sa-east-1 e recebe o HTML da página de detalhe para analisar.
// Segurança: exige a chave do projeto (verify_jwt), só aceita POST e números de processo,
// e só acessa busca.inpi.gov.br (não é proxy aberto). Não usa banco de dados.
import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const BASE = "https://busca.inpi.gov.br/pePI/servlet/MarcasServletController";
const LOGIN = "https://busca.inpi.gov.br/pePI/servlet/LoginController?action=login";
const HEADERS = {
  "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
  "Origin": "https://busca.inpi.gov.br",
  "Referer": "https://busca.inpi.gov.br/pePI/jsp/marcas/Pesquisa_num_processo.jsp",
  "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
};
const TIMEOUT_MS = 20000;
const REGIAO = Deno.env.get("SB_REGION") ?? "desconhecida";

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json; charset=utf-8" } });

const latin1 = async (r: Response) => new TextDecoder("windows-1252").decode(await r.arrayBuffer());

function cookiesDe(r: Response, atual: string): string {
  const mapa = new Map<string, string>();
  const guardar = (par: string) => {
    const i = par.indexOf("=");          // indexOf, não split: o valor pode conter "="
    if (i > 0) mapa.set(par.slice(0, i).trim(), par.slice(i + 1).trim());
  };
  atual.split(";").forEach(guardar);
  for (const sc of r.headers.getSetCookie()) guardar(sc.split(";")[0]);
  return [...mapa].map(([k, v]) => `${k}=${v}`).join("; ");
}

function classificar(e: unknown, etapa: string) {
  const nome = (e as Error)?.name ?? "";
  const msg = String((e as Error)?.message ?? e);
  if (nome === "TimeoutError" || nome === "AbortError")
    return { status: "inpi_timeout", etapa, erro: `O INPI não respondeu em ${TIMEOUT_MS / 1000} s (${etapa}).` };
  return { status: "inpi_conexao", etapa, erro: `Falha de conexão com o INPI (${etapa}): ${msg}` };
}

Deno.serve(async (req) => {
  if (req.method !== "POST")
    return json({ status: "metodo_invalido", erro: "Use POST com corpo JSON." }, 405);

  const t0 = Date.now();
  let corpo: Record<string, string> = {};
  try { corpo = await req.json(); } catch (_) { /* corpo vazio ou inválido */ }
  const acao = corpo.acao ?? "consultar";
  let cookie = typeof corpo.cookie === "string" ? corpo.cookie : "";

  // ping: testa se o INPI está acessível a partir desta região (usado pelo app ao iniciar)
  if (acao === "ping") {
    try {
      const r = await fetch(LOGIN, { headers: HEADERS, signal: AbortSignal.timeout(TIMEOUT_MS) });
      cookie = cookiesDe(r, "");
      await r.body?.cancel();
      return json({ status: "ok", regiao: REGIAO, http: r.status, cookie, ms: Date.now() - t0 });
    } catch (e) {
      return json({ ...classificar(e, "sessão"), regiao: REGIAO, ms: Date.now() - t0 }, 502);
    }
  }

  const processo = String(corpo.processo ?? "").replace(/\D/g, "");
  if (!/^\d{6,12}$/.test(processo))
    return json({ status: "entrada_invalida", erro: "Número de processo inválido (use só dígitos).", regiao: REGIAO }, 400);

  let etapa = "sessão";
  try {
    if (!cookie) {
      const r0 = await fetch(LOGIN, { headers: HEADERS, signal: AbortSignal.timeout(TIMEOUT_MS) });
      cookie = cookiesDe(r0, "");
      await r0.body?.cancel();
    }
    etapa = "busca";
    const r1 = await fetch(BASE, {
      method: "POST",
      headers: { ...HEADERS, "Content-Type": "application/x-www-form-urlencoded", Cookie: cookie },
      body: new URLSearchParams({ Action: "searchMarca", NumPedido: processo, tipoPesquisa: "BY_NUM_PROC" }),
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    cookie = cookiesDe(r1, cookie);
    const html1 = await latin1(r1);
    if (r1.status !== 200)
      return json({ status: "inpi_http", etapa, erro: `O INPI respondeu HTTP ${r1.status} na busca.`, regiao: REGIAO, cookie }, 502);
    if (html1.toLowerCase().includes("nenhum resultado foi encontrado"))
      return json({ status: "nao_encontrado", regiao: REGIAO, cookie, ms: Date.now() - t0 });

    const m = html1.match(/Action=detail&CodPedido=(\d+)/);
    let detalhe = html1;
    if (m) {
      etapa = "detalhe";
      const r2 = await fetch(`${BASE}?Action=detail&CodPedido=${m[1]}`, {
        headers: { ...HEADERS, Cookie: cookie }, signal: AbortSignal.timeout(TIMEOUT_MS),
      });
      cookie = cookiesDe(r2, cookie);
      detalhe = await latin1(r2);
    } else if (!html1.includes("Marca:")) {
      return json({
        status: "pagina_inesperada", etapa,
        erro: "A página do INPI veio em formato inesperado (layout mudou ou sessão expirou).",
        trecho: html1.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").slice(0, 300), regiao: REGIAO, cookie,
      }, 502);
    }
    return json({ status: "ok", html: detalhe, regiao: REGIAO, cookie, ms: Date.now() - t0 });
  } catch (e) {
    return json({ ...classificar(e, etapa), regiao: REGIAO, cookie }, 502);
  }
});
