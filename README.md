# Bot de Monitoramento de Promoções

Monitora preços de produtos (começando pela Amazon), detecta quedas de
preço, converte o link em link de afiliado e posta automaticamente num
canal do Telegram. Roda de graça a cada hora via GitHub Actions.

## Como funciona

```
main.py
  -> scraper/amazon.py       busca preço/nome/disponibilidade via Bright Data
  -> storage/price_history.py compara com o último preço salvo (SQLite)
  -> telegram/notifier.py     posta no canal se a queda for >= threshold
```

O histórico de preços fica em `data/price_history.db` e é commitado de
volta no repositório a cada execução do workflow.

## 1. Criar o bot no Telegram

1. Abra uma conversa com [@BotFather](https://t.me/BotFather) no Telegram.
2. Envie `/newbot` e siga as instruções (nome + username do bot).
3. O BotFather vai te dar um token no formato `123456:ABC-DEF...`. Esse é
   o seu `TELEGRAM_BOT_TOKEN`.

## 2. Pegar o chat_id do canal

1. Crie um canal no Telegram (ou use um existente) e adicione o bot como
   **administrador** do canal.
2. Poste qualquer mensagem no canal.
3. Acesse `https://api.telegram.org/bot<SEU_TOKEN>/getUpdates` no
   navegador (substitua `<SEU_TOKEN>` pelo token do bot).
4. Procure o campo `"chat":{"id":-100XXXXXXXXXX, ...}` na resposta — esse
   número (com o sinal de menos) é o seu `TELEGRAM_CHAT_ID`.

Se `getUpdates` não retornar nada, poste outra mensagem no canal e tente
de novo (o Telegram só guarda updates recentes não consumidos).

## 3. Pegar a chave do Bright Data

1. Crie uma conta em [brightdata.com](https://brightdata.com) e acesse o
   painel.
2. Em **Settings > API keys**, gere um token de API — esse é o
   `BRIGHTDATA_API_TOKEN`.
3. Em **Web Scraper API**, procure o dataset pronto **"Amazon Products"**
   (ou crie uma coleta a partir dele) e copie o **Dataset ID**
   (formato `gd_xxxxxxxxxxxx`) — esse é o `BRIGHTDATA_AMAZON_DATASET_ID`.

O scraper (`scraper/brightdata_client.py`) usa a Web Scraper API do
Bright Data: dispara uma coleta para as URLs configuradas, aguarda o
snapshot ficar pronto e baixa os dados já estruturados (nome, preço,
disponibilidade) — sem precisar de parser manual de HTML.

> Os nomes dos campos retornados (`title`, `final_price`, `availability`,
> etc.) seguem o schema atual do dataset "Amazon Products" do Bright
> Data. Se o Bright Data atualizar o schema, ajuste o mapeamento em
> `scraper/amazon.py` (`_parse_record`).

## 4. Cadastrar produtos

Edite `config/products.json`:

```json
[
  {
    "id": "echo-dot-5",
    "url": "https://www.amazon.com.br/dp/B09B8V1LZ3",
    "name": "Echo Dot 5ª Geração"
  }
]
```

- `id`: identificador único e estável do produto (usado para achar o
  histórico dele — não mude depois de já ter rodado).
- `url`: URL do produto na Amazon.
- `name`: nome de exibição (opcional — se omitido, usa o nome retornado
  pelo Bright Data).

## 5. Configurar link de afiliado

Defina `AMAZON_AFFILIATE_TAG` com sua tag de afiliado da Amazon (ex:
`seunome-20`). O bot substitui os parâmetros da URL original pelo
`?tag=<sua_tag>` antes de postar. Se a variável ficar vazia, o link é
postado sem afiliado (não quebra o fluxo).

## 6. Configurar variáveis localmente

```bash
cp .env.example .env
# preencha .env com os valores acima
pip install -r requirements.txt
python main.py
```

## Rodar os testes

Os testes usam fakes/mocks para Bright Data e Telegram — não fazem
chamada de rede real nem exigem `.env` preenchido.

```bash
pip install -r requirements-dev.txt
pytest -v
```

## 7. Configurar os secrets no GitHub Actions

No repositório do GitHub, vá em **Settings > Secrets and variables >
Actions** e cadastre como **secrets**:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `BRIGHTDATA_API_TOKEN`
- `BRIGHTDATA_AMAZON_DATASET_ID`
- `AMAZON_AFFILIATE_TAG`

Opcionalmente, cadastre como **variable** (não secret):

- `PRICE_DROP_THRESHOLD_PERCENT` (padrão: `15`)

O workflow (`.github/workflows/check-prices.yml`) já está configurado
para rodar `python main.py` a cada hora (`cron: "0 * * * *"`) e também
pode ser disparado manualmente pela aba **Actions** (`workflow_dispatch`).
Ele tem permissão `contents: write` para poder commitar o
`data/price_history.db` atualizado de volta no repositório a cada
execução — isso não precisa de nenhum PAT extra, o `GITHUB_TOKEN` padrão
já é suficiente.

## Ajustar o intervalo do cron

Edite o `cron` em `.github/workflows/check-prices.yml`. Exemplos:

- A cada hora: `"0 * * * *"` (padrão)
- A cada 30 min: `"*/30 * * * *"`
- A cada 6 horas: `"0 */6 * * *"`

O GitHub Actions não garante o horário exato em cron schedules — pode
atrasar alguns minutos em horários de pico.

## Limitações conhecidas

- O free tier do GitHub Actions em repositórios públicos é ilimitado;
  em repositórios privados há um limite de minutos/mês — um cron de 1h
  usa bem pouco disso.
- O Bright Data cobra por uso da Web Scraper API — verifique os limites
  do seu plano antes de aumentar a frequência ou a lista de produtos.
- O SQLite é commitado como arquivo binário: os diffs no histórico do
  Git não serão legíveis, só o conteúdo do banco.
