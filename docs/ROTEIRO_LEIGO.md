# Roteiro para leigo: colocar o Offer Scout no ar (PC + iPhone)

Você vai precisar do PC só para a **montagem inicial** (cerca de 30 a 40 minutos). Depois, tudo se acompanha pelo iPhone.
Os nomes de botões e menus do GitHub mudam de vez em quando. Se algo não bater com este texto, tire um print e me mande.

## O que você terá no final
- Um endereço (link) com o painel, que você abre no iPhone como se fosse um app.
- Uma busca automática toda segunda-feira, às 6h (Brasília), que atualiza o painel sozinha.
- Ideias de publicação para Brasil, EUA e Europa, sempre com a evidência por trás.
- **Nada é publicado, vendido nem pago sozinho.** O sistema só pesquisa e sugere. Quem decide é você.

## Antes de começar
1. Use um PC **pessoal ou de confiança**. No computador do trabalho, confirme se a empresa permite usar o equipamento para um projeto pessoal. Não deixe senhas salvas nele.
2. Tenha um e-mail seu à mão.
3. Baixe o arquivo **offer-scout.zip** (ele está no nosso chat) e envie para o PC (AirDrop, iCloud, e-mail para você mesmo ou cabo).

## Parte 1: no PC
### Passo 1. Criar a conta no GitHub
1. Abra github.com e clique em **Sign up**. Crie a conta com seu e-mail.
2. Ative a verificação em duas etapas (Settings → Password and authentication). Ela protege a conta.

### Passo 2. Criar o repositório (a "pasta" na nuvem)
1. Clique no **+** no canto superior direito → **New repository**.
2. Nome: `offer-scout`. Marque **Private**. Clique em **Create repository**.

### Passo 3. Enviar os arquivos
1. No PC, **descompacte** o `offer-scout.zip` (botão direito → Extrair tudo).
2. Abra a pasta descompactada. Selecione **tudo que está dentro dela** (não a pasta externa).
3. No GitHub, na página do repositório, clique em **uploading an existing file** (ou Add file → Upload files).
4. **Arraste** a seleção para a janela. Espere carregar.
5. Role até o fim e clique em **Commit changes**.
   - Se o GitHub reclamar do número de arquivos, envie em duas levas: primeiro as pastas `src`, `config` e `site`; depois o resto.

### Passo 4. Criar o arquivo de agendamento (importante)
As pastas que começam com ponto, como `.github`, às vezes não vão no arrasto, principalmente no Mac. Por isso vamos criar esse arquivo à mão:
1. No repositório, clique em **Add file → Create new file**.
2. No campo do nome, digite exatamente: `.github/workflows/scout.yml` (ao digitar a barra `/`, o GitHub cria as pastas).
3. Abra o arquivo `scout.yml` da pasta descompactada com o Bloco de Notas (no Mac, tecle Cmd+Shift+. para ver pastas ocultas). Copie **todo o conteúdo** e cole no GitHub.
4. Clique em **Commit changes**.

### Passo 5. Ligar o painel online
1. No repositório, clique em **Settings** → **Pages** (menu da esquerda).
2. Em **Build and deployment → Source**, escolha **GitHub Actions**.

### Passo 6. Primeiro teste, com dados FALSOS
Isso confirma que a montagem funcionou, sem precisar de nenhuma chave.
1. Clique na aba **Actions**. Se pedir, clique em **I understand my workflows, enable them**.
2. Clique em **Offer Scout** (menu da esquerda) → **Run workflow**. Marque a caixa **simulate** e confirme.
3. Espere 2 a 5 minutos até aparecer um ✓ verde. Se aparecer ✗ vermelho, abra a execução, copie a mensagem de erro e me mande.
4. Volte em Settings → Pages. O endereço do seu painel aparece no topo.

Nesse teste o painel mostra um aviso vermelho de **"Dados SIMULADOS"**. É esperado: são números fictícios, só para testar. Não decida nada com eles.

## Parte 2: no iPhone
1. Abra o endereço do painel no **Safari**.
2. Toque no ícone de compartilhar → **Adicionar à Tela de Início**.
3. Pronto: ele abre como um app. Atualiza sozinho a cada 5 minutos e quando você volta para ele.

### Como ler o painel
- **Nota (0 a 100):** soma de demanda, persistência, qualidade, viabilidade e diferenciação, menos penalidades. Toque no cartão para ver como foi composta.
- **Decisão:** *Validar* = vale um teste barato antes de construir. *Observar* = evidência fraca. *Rejeitar* = fora de escopo ou fraco.
- **Confiança:** quase sempre *baixa* até haver dados reais de anúncios e vendas. Baixa significa: não invista dinheiro só com isso.
- **Aba Mercados:**
  - *Lacuna com evidência*: há vários vendedores no mercado de origem e poucos no mercado de destino, e a busca realmente cobriu o destino.
  - *Sem verificação*: não há como saber, porque faltaram dados ou a busca nesse idioma ainda não existe.
  - *Já concorrido*: já há vendedores no destino.
  - Poucos concorrentes **não** significam oportunidade garantida. Pode ser que ninguém queira comprar. Cada ideia traz o próximo passo para conferir isso.

## Parte 3: dados reais (volte ao PC quando quiser)
Sem chaves, o sistema não tem de onde puxar dados e o painel avisa **"Sem fontes configuradas"**. Você tem três caminhos, que podem ser combinados:

**A. Etsy (vitrine de produtos digitais).** Crie um app em etsy.com/developers e peça a chave de API. O Etsy aprova manualmente e pode demorar ou negar. Depois, no GitHub: Settings → Secrets and variables → Actions → **New repository secret**. Nome `ETSY_API_KEY`, valor = a chave.

**B. Meta Ad Library (anúncios).** Crie um app em developers.facebook.com e confirme sua identidade (a Meta exige). Gere um token e salve como secret `META_AD_LIBRARY_TOKEN`. **Limite importante:** até onde sei, essa API só traz anúncios comerciais da Europa e do Reino Unido. Para EUA e Brasil ela não serve.

**C. Planilhas (CSV) soltas na pasta `data/inbox`.** É o caminho para Brasil e EUA onde não há API.
- Você pode exportar listas de ferramentas pagas de inteligência de anúncios, ou do Google Trends (botão de download CSV no gráfico).
- Mande o arquivo aqui no chat. Eu converto para o formato do Scout e te devolvo pronto. Depois, no GitHub: pasta `data/inbox` → Add file → Upload files. Isso dispara uma execução sozinha.

**Nunca cole senhas ou chaves no chat nem em arquivos do repositório.** Só no campo Secrets.

## Brasil e Europa: o que esperar
- A busca usa termos em **português (Brasil), alemão, francês e espanhol**. As traduções são aproximadas: peça a um falante nativo para revisar antes de basear uma decisão nelas.
- Para Brasil e Europa, o Etsy é só um dos canais. Plataformas locais (por exemplo Hotmart, Kiwify ou Eduzz no Brasil) não têm uma busca pública oficial que eu conheça, então entram por CSV.
- O painel avisa quando um mercado tem poucos dados (menos de 20 registros) e, nesse caso, **não afirma lacuna**.
- Impostos, direito de arrependimento e proteção de dados mudam por país. Os avisos que o painel mostra são lembretes para confirmar com contador ou advogado, não orientação legal.

## Rotina semanal de 5 minutos (iPhone)
1. Abra o painel. Veja se há caixa vermelha ou amarela no topo.
2. Leia as oportunidades em *Validar* e a aba *Mercados*.
3. Se algo interessar, me mande aqui: o próximo passo é o Agente 2 (Modeler) criar uma oferta original.

## Problemas comuns
- **Painel mostra "Ainda não há dados":** a primeira execução ainda não terminou ou falhou. Veja a aba Actions.
- **Caixa vermelha "A última execução falhou":** abra Actions → a execução com ✗ → copie o erro e me mande.
- **Execução verde, mas "Sem fontes configuradas":** falta chave ou CSV (Parte 3).
- **Actions não aparece rodando na segunda:** repositórios sem atividade por 60 dias podem ter o agendamento pausado pelo GitHub. Rode manualmente com Run workflow para reativar.
- **O link do painel está público:** o endereço do GitHub Pages pode ser aberto por quem tiver o link, mesmo com o repositório privado. Não compartilhe o link. Se isso for um problema, me avise e eu adapto para hospedar com acesso restrito.
