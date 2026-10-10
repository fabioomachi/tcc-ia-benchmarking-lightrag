# POP – Gestão de Senhas e Código de Acesso – Pessoa Física
### [Versão anonimizada/pseudonimizada — documento complementar ao POP de CDC]

> **Nota metodológica:** este documento usa a mesma metodologia e os mesmos pseudônimos institucionais do POP de CDC anonimizado anteriormente (Banco Alfa, SISALFA, App Alfa etc.). Termos novos e específicos deste documento (produtos de cartão, plataformas, rotinas) foram adicionados à mesma chave de correspondência (arquivo único, cumulativo). A lógica processual e as condições originais foram mantidas integralmente.

**Sumário:** Notas iniciais · 1. Resumo das senhas · 2. Situação das senhas · 3. Correntistas e poupadores · 4. Não correntista · 5. Código de acesso · 6. Geração de senha PF · 7. Cliente no exterior · 8. Senha do portador adicional · 9. Acesso ao gov.br · 10. Central de Senhas PF · 11. Fontes de informação · 12. Rotinas absorvidas

---

## Notas iniciais

a) **Transferência de saldo/produtos entre agências:** a senha da agência de origem não é alterada; o cliente acessa normalmente a conta na agência de destino.

b) Os procedimentos desta rotina não se aplicam a clientes PJ ou Setor Público. Para chave J e senhas (Alfa Digital PJ), ver rotina 50129.

c) **Titulares solidários:** as senhas (6 e 8 dígitos) e o código de acesso são os mesmos para todos os titulares. Se um titular bloquear a senha, os demais ficam impossibilitados de realizar transações.

d) **Push:** notificação recebida diretamente no App Alfa. Para ativar: 1) autorizar o App Alfa no sistema do celular (Android: Configurações > Receber Notificações; iOS: Ajustes > Receber Notificações); 2) ativar pelo App Alfa (área logada) em Perfil > Geral > Receber notificações.

e) **Bloqueio de Canal:** consulte na plataforma em Segurança > Bloqueio de segurança > Histórico. Havendo bloqueio, o desbloqueio ocorre após a alteração das senhas de 6 e 8 dígitos — é obrigatório alterar primeiro a de 8 dígitos, depois a de 6. Use os itens 3 e/ou 4 para orientar os canais.

---

## 1. Resumo da utilização das senhas

| Tipo de senha | Canais de utilização |
|---|---|
| Senha de 4 dígitos | Descontinuada |
| Senha de 6 dígitos | Confirma transações de cartão débito e crédito. Plataforma de Relacionamento/URA: acesso, consulta e confirmação de transações da mesma titularidade. Site institucional (sem Alfa Code): confirmação de transações financeiras. App Alfa: confirmação de transações financeiras. WhatsApp Alfa: pode ser solicitada para confirmação de algumas transações. TCX, TAD, POS, correspondente bancário: confirmação de transações. TAA: confirmação de transações de beneficiários do INSS e de portadores de deficiência visual sem código de acesso. Banco 24 Horas e rede compartilhada (Banco Parceiro Beta): confirmação de transações de portadores de deficiência visual sem código de acesso. |
| Senha de 8 dígitos | Site institucional, App Alfa, App Cartão Alfa e WhatsApp: acesso, consultas, transações financeiras e aquisição de produtos/serviços. |
| Código de Acesso (letras, sílabas ou alfanumérico) | TAA, Banco 24 Horas e rede compartilhada: confirma transações, inclusive saques na função crédito do cartão. |
| Conta de Acesso (senha alfanumérica) | Utilizada por não correntistas no App Alfa (versão não correntista). |

---

## 2. Situação das Senhas

### 2.1. Consultas
- Senhas de 6/8 dígitos e código de acesso — Quadro Próprio e Quadro Contratado: `SISALFA > SISRET > X69 > 2` (correntistas: agência e conta; não correntistas: número do cartão), campo STATUS (pode ser informado ao cliente).
- Conta de Acesso (Quadro Próprio): `SISALFA > ACESSO > 32 > 01 > CPF`.

### 2.2. Códigos aplicáveis a TODOS os tipos de senha
| Código | Significado | Situação |
|---|---|---|
| 0 | Sem ocorrência de erro de digitação | Ativa |
| 1 | Cliente errou a digitação uma vez | — |
| 2 | Cliente errou a digitação duas vezes | — |
| 3 | Cliente errou a digitação três vezes (se ocorrer na senha de 6 dígitos via APF, Mobile ou WhatsApp, o bloqueio "3" é aplicado também à senha de 8 dígitos) | Bloqueada |
| 6 | Senha (PJ e Governo) cadastrada no Alfa Digital PJ, aguardando confirmação de um funcionário da agência | — |
| 7 | Senha (PJ e Governo) cadastrada no Alfa Digital PJ, aguardando confirmação de dois funcionários da agência | — |
| Q | Senha alterada no APF Internet sem Alfa Code, ou no APF Celular sem fotografar cartão válido (aguardando confirmação na TAA com biometria cadastrada há mais de 7 dias) | — |
| U | Senha bloqueada pelo monitoramento de segurança dos canais de autoatendimento | — |

### 2.3. Códigos exclusivos da senha de 6 dígitos
| Código | Significado | Situação |
|---|---|---|
| A | Senha digitada errada 3 vezes | Bloqueada |
| D | Erro na tentativa de desbloqueio na TAA, ou bloqueio feito pelo próprio cliente via APF Celular/Internet | — |

### 2.4. Códigos exclusivos da senha de 8 dígitos
| Código | Significado | Situação |
|---|---|---|
| T | Senha registrada antes de 2012 e bloqueada por não uso nos últimos 90 dias | Bloqueada |
| D | Alteração iniciada via APF Celular, com falha na confirmação via TAA sem biometria | — |
| P | Senha cadastrada via APF Internet/Celular, aguardando confirmação na TAA | — |
| 4 | Erro na tentativa de desbloqueio via Mobile | — |
| 8 | Senha bloqueada pela agência ou pelo próprio cliente nos canais de autoatendimento | — |

### 2.5. Situações do código de acesso
Código "4" = tentativa de desbloqueio na TAA; CAA = letras; CAS = sílabas; CAN = alfanumérico.

### 2.6. Situações da senha alfanumérica (Conta de Acesso)
*Solicitado* = cadastramento/alteração pedidos; *Ativa* = cadastrada e ativa; *Bloqueado* = bloqueada por erro de digitação ou por segurança.
> Essa confirmação ocorre por oferta ativa, sem necessidade de navegar pelo menu da TAA.

---

## 3. Correntistas e Poupadores

### 3.1. Senha de 6 dígitos (conta e cartão)

Usada para autorizar transações em: terminais de caixa das agências, TAA, site institucional (sem Alfa Code), App Alfa, correspondente bancário, transações de cartão (débito e crédito) e acesso à Central de Relacionamento/SAC. Vinculada à agência/conta (correntista) ou ao CPF (não correntista).

**3.1.1. Cadastramento**

| Canal | Procedimento |
|---|---|
| Agência | Correntistas e poupadores: no fluxo de abertura de conta, em qualquer agência. Beneficiários do INSS: em qualquer agência. Clientes de conta digital: no fluxo de abertura pelo App Alfa. |

> **Atenção:** se o cliente quiser encerrar a conta corrente e ficar só com o cartão de crédito, cadastre nova senha como não correntista — obrigatório para não deixar pendente a emissão dos cartões.

**3.1.2. Alteração**

> Para cartões com chip, após a alteração, oriente o cliente a atualizar o chip de todos os plásticos em qualquer TAA (sob risco da senha não funcionar). Verifique a possibilidade de enviar senha provisória por SMS (item 6).

| Canal | Requisitos/Condição | Procedimento |
|---|---|---|
| App Alfa | Celular autorizado há mais de 30 dias; Alfa Code ou Push habilitado; geolocalização ativa e autorizada; cartão ativo; senha de 8 dígitos ativa (códigos 0, 1 e/ou 2). Não disponível se bloqueada por "8". | **Com a senha anterior:** área logada > Perfil > Segurança > Central de senhas > Senha de 6 dígitos > Alterar. **Sem a senha anterior:** área logada > Perfil > Segurança > Central de senhas > Senha de 6 dígitos > Esqueci a senha > "Agora utilizando o cartão" (dados do cartão) — confirmação por: (i) biometria na TAA (cadastrada há mais de 7 dias): App Alfa > Menu > Perfil > Central de senhas > Senha de 6 dígitos > Esqueci a senha > No caixa eletrônico, depois na TAA em Segurança e Senhas > Senhas > Liberação de Senha Provisória > Senha da conta e cartão (6 dígitos); ou (ii) WhatsApp (telefone cadastrado no ATO): área logada > Perfil > Central de senhas > Senha de 6 dígitos > Esqueci a senha > Por WhatsApp. |
| Site institucional | Senha de 8 dígitos ativa (códigos 0, 1 e/ou 2). Não disponível para quem não usa Alfa Code e não tem biometria cadastrada há mais de 7 dias (ou de forma assistida), nem para bloqueio "U" ou "8" da senha de 6 dígitos. | Em computador autorizado, com ou sem a senha anterior: **com adesão ao Alfa Code:** área logada > Segurança > Senhas > Alterar > Senha do cartão (6 dígitos) (exige código de autorização do Alfa Code). **Sem adesão ao Alfa Code, com biometria cadastrada:** mesmo caminho, confirmando em uma TAA com biometria cadastrada há mais de 7 dias. |
| Agências (inclusive bloqueio "U") | — | Mediante identificação; recomendar que o cliente leve o cartão. |
| SAC | Bloqueio "U": SAC Receptivo QP/QC (Célula de Segurança) → rotina 50130; SAC Soluções QP → rotina 50131; SAC Quadro Contratado → rotina 50112. Outros bloqueios: SAC Quadro Próprio → procedimento de Geração de Senha (item 6); SAC Quadro Contratado → rotina 50112. | — |
| Plataforma de Relacionamento / ATA | Exceto bloqueio "U": Quadro Próprio → Geração de Senha; Quadro Contratado (não correntista portador de cartão) → Geração de Senha; correntistas/poupadores → demais canais. | — |

**3.1.3. Bloqueio**

Canais por iniciativa do cliente: TAA; SAC QC/QP; Plataforma de Relacionamento; site institucional (com Alfa Code); App Alfa (dispositivo autorizado, com Alfa Code ou push); agências.
> Se o cliente detectar lançamentos indevidos na conta (inclusive por invasão do site), utilize também a rotina 50136, item 5.1. Bloqueio por um titular solidário impede os demais de transacionar. O bloqueio do código de acesso implica bloqueio da senha de 6 dígitos.

**3.1.4. Desbloqueio**

Feito COM conhecimento da senha anterior (sem isso, é preciso fazer a Alteração). Bloqueio "U" não admite desbloqueio, só Alteração.

| Canal | Requisitos | Procedimento |
|---|---|---|
| App Alfa | Celular autorizado >30 dias; Alfa Code/Push habilitado; geolocalização ativa; cartão ativo; senha de 8 dígitos ativa (0,1,2). | Área logada > Perfil > Segurança > Central de senhas > Senha de 6 dígitos > Desbloquear. |
| Site institucional | Senha de 8 dígitos ativa (0,1,2). | Em computador autorizado — com Alfa Code: Segurança > Senhas > Desbloquear (código de autorização); sem Alfa Code: mesmo caminho, confirmando em TAA com biometria (>7 dias). |
| TAA | Biometria, ou cartão + código de acesso. | Menu > Segurança e Senhas > Senhas > Desbloqueio > Senha da conta e cartão (6 dígitos). |
| Agência | Identificação (recomendar levar o cartão). | — |

> Erro de digitação na tentativa de desbloqueio na TAA: só pode ser desbloqueada em agência. Bloqueio por iniciativa da agência/cliente: desbloqueio em qualquer agência. Bloqueio por erro de identificação positiva na TAA: só desbloqueia em agência (se o cliente souber a senha); usar a TAA para essa operação não é possível. Desbloqueio exige código de acesso ou biometria; sem nenhum dos dois, é necessário comparecer a uma agência.

### 3.2. Senha de 8 dígitos

Acessa o site institucional e o App Alfa; pode ser provisória¹ ou definitiva. Confirmação de transações financeiras via Alfa Code; sem Alfa Code, usa-se a senha de 6 dígitos (oriente o cadastramento do Alfa Code). Senha única — não precisa ser cadastrada por cada titular.

> ¹ Provisória: só senhas antigas; acesso restrito a consultas. Para movimentações financeiras, deve ser liberada em uma TAA.

**3.2.1. Cadastramento**

| Canal | Procedimento |
|---|---|
| App Alfa | Correntistas/poupadores: "Esqueci ou não tenho a senha" na tela de login (clientes sem histórico de equipamento autorizado no ATO); o equipamento fica em carência (há um link de liberação). Clientes de conta digital: cadastram no fluxo de abertura via Mobile. |
| TAA | Com biometria cadastrada há mais de 7 dias: Menu > Segurança e Senhas > Senhas > Cadastramento. |
| Agência | Qualquer agência, informando a senha de 6 dígitos. |

**3.2.2. Alteração**

| Canal | Condição | Procedimento |
|---|---|---|
| App Alfa | Celular autorizado >30 dias; Alfa Code/Push; geolocalização; cartão ativo. | **Com a senha atual:** área logada > Perfil > Segurança > Central de senhas > Senha de 8 dígitos > Alterar (digitar a senha atual). **Sem a senha atual (inclusive bloqueio ≠ "U"), ou bloqueio "U":** "Esqueci minha senha" (tela de login ou tela inicial não logada) > Recuperar senha > Senha de 8 dígitos > Esqueci a senha, com 3 opções: (i) "Agora utilizando o cartão" (dados do cartão, dispositivo autorizado, Alfa Code ou Push); (ii) "No caixa eletrônico" (confirmação por biometria na TAA, cadastrada há mais de 7 dias); (iii) por WhatsApp (telefone cadastrado no ATO + versão mínima do app + reconhecimento facial). *A opção "recuperar senha" só aparece em celular autorizado onde o cliente já acessou a conta ao menos uma vez.* |
| Site institucional (computador autorizado) | Com a senha atual: exigida a senha de 8 dígitos atual. | **Com Alfa Code:** Segurança > Senhas > Alterar > Senha da internet (8 dígitos) (código de autorização). **Sem Alfa Code:** mesmo caminho, confirmando em TAA com biometria (>7 dias). Sem a senha atual (inclusive bloqueio ≠ "U"), ou bloqueio "U": não disponível neste canal. |
| TAA | Com ou sem a senha atual (inclusive bloqueios). | Menu > Segurança e Senhas > Senhas > Alteração > Senha de acesso à internet e ao celular (8 dígitos). Com biometria: qualquer horário (cadastrada há mais de 7 dias, ou de forma assistida). Sem biometria, com cartão com chip + código de acesso: das 10h às 16h em dias úteis. |
| Agência | Com ou sem a senha atual (inclusive bloqueios). | Atendimento presencial, exigindo a senha de 6 dígitos; recomendar levar o cartão. |
| SAC | Com a senha atual, ou sem ela (exceto "U"): Quadro Próprio → Geração de Senha; Quadro Contratado → rotina 50112. Bloqueio "U": SAC Receptivo (Célula de Segurança) → rotina 50130; SAC Soluções QP → rotina 50131; SAC QC → rotina 50112. | — |
| Plataforma de Relacionamento / ATA | Com a senha atual, ou sem ela (exceto "U"): Quadro Próprio → Geração de Senha; Quadro Contratado (não correntista com cartão) → Geração de Senha; correntistas/poupadores → demais canais. Bloqueio "U": não disponível neste canal. | — |

**3.2.3. Bloqueio**

Canais por iniciativa do cliente: TAA; SAC; agências; site institucional (com Alfa Code); App Alfa (dispositivo autorizado, com Alfa Code ou push). Bloqueio de segurança ocorre quando há indício de violação da senha. Bloqueio "T": não é mais aplicado — restam apenas registros até 2012.

**3.2.4. Desbloqueio**

> Sem conhecimento da senha anterior, bloqueio "U" (segurança) ou bloqueio "4": seguir os procedimentos de Alteração.

Consulte em `SISRET X69 > 02` (correntistas: agência/conta; não correntistas: número do cartão), campo STATUS, ou pela Plataforma (Segurança > Senhas > Gerenciamento de Senhas). Não pergunte data de validade nem CVV ao cliente — preencha o número do cartão, use o mês/ano do contato como validade e "000" no CVV2.

| Tipo de bloqueio | Canal | Procedimento |
|---|---|---|
| Por iniciativa da agência ou do cliente | Agência | Com a senha de 6 dígitos (recomendar levar o cartão). |
| | TAA | Com código de acesso ou biometria. |
| Por motivo "T" | Agência | Idem acima. |
| | TAA | Idem acima. |
| Por digitação incorreta 3 vezes | App Alfa (dispositivo autorizado >30 dias, Alfa Code/Push, geolocalização, cartão ativo) | Recuperar Senhas > Senha de 8 dígitos > Desbloquear (digitar a senha atual). |
| | Agência | Com a senha de 6 dígitos. |
| | TAA | Com código de acesso ou biometria. |
| Por erro na tentativa de desbloqueio na TAA | Agência | Com a senha de 6 dígitos. |

---

## 4. Não Correntista

### 4.1. Senha de 6 dígitos

**4.1.1. Cadastramento:** clientes não correntistas que solicitam Cartão Alfa via App ou web cadastram no próprio fluxo de solicitação. Private Label → rotina 50133. Cartões de programa de fidelidade parceiro → rotina 50134.

**4.1.2. Alteração:** Agência (qualquer uma, com cartão válido e identificação); SAC e Plataforma de Relacionamento → item 6 desta rotina.

**4.1.3. Bloqueio:** por iniciativa do cliente — TAA; SAC QC/QP; Plataforma de Relacionamento; agências.

**4.1.4. Desbloqueio:** Agência (qualquer uma, com a senha de 6 dígitos); TAA (com o código de acesso).

### 4.2. Conta de Acesso e Senha de 8 dígitos

**Demanda:** dificuldade para acessar o App Alfa ou o App Cartão Alfa com a senha de 8 dígitos.

> **Atenção:** há 2 tipos de senha de 8 dígitos para não correntista — **Conta de Acesso** (acessa o App Alfa) e **Senha-8** (acessa o App Cartão Alfa). O cliente normalmente não sabe dessa distinção. Para identificar o tipo, siga o item 4.2.1.

**4.2.1. Identificação do tipo de senha**

*4.2.1.1. Sistema Alfa:*
- a) Senha Conta de Acesso: `SISRET X69 > 02 > nº do cartão`. Se "não localizado" ou se o cliente tiver os dois tipos, siga para (b). Se possuir só Conta de Acesso: Quadro Contratado → siga para 4.2.2; Quadro Próprio → confira a situação (se "Ativo", tecle F9 para mais detalhes) e siga para 4.2.2.
- b) Senha-8: `SISALFA > SISRET X69 > 02 > nº do cartão`. Cliente com só Senha-8, ou com as duas → oriente conforme 4.2.2 (Quadro Próprio e Contratado).

*4.2.1.2. Plataforma:* não pergunte data de validade nem CVV. `Plataforma de Negócios > Segurança > Senhas > Gerenciamento de Senhas 3.0` — preencha o número do cartão, use o mês/ano do contato como validade e "000" no CVV2.

**4.2.2. Procedimentos** (se o cliente tiver os dois tipos, pergunte qual app ele quer acessar):

| Senha | Cadastramento | Alteração | Bloqueio | Desbloqueio |
|---|---|---|---|---|
| **Conta de Acesso** (App Alfa) | No momento da contratação do cartão (App Alfa/onboarding digital) | App Alfa (Central de Senhas) ou link de recuperação; Agência (cartão válido e previamente liberado) | Agência | Agência (cartão válido e previamente liberado) |
| **Senha-8** (App Cartão Alfa) | No momento da contratação do cartão (lojas parceiras, correspondentes, agências) | TAA; SAC e Plataforma de Relacionamento (Geração de Senha, ou outros canais); App Cartão Alfa "Esqueci minha senha" (sem bloqueio vigente); Agência | TAA; APF; Mobile; agências; **se o cliente foi vítima de assalto, roubo ou sequestro:** SAC QP/QC e Plataforma de Relacionamento → `SISRET X98`, código de rota 800050, conta = nº da conta do cartão | TAA; Agência |

> Não correntistas com Conta de Acesso também podem acessar o App Cartão Alfa, mas precisam cadastrar uma senha de 8 dígitos separada via "Esqueci senha" — explique que serão duas senhas diferentes, uma para cada app. Quem possui só a Senha-8 NÃO consegue acessar o App Alfa.

---

## 5. Código de Acesso (Alfanumérico)

a) **Deficientes visuais:** o cliente com deficiência visual total pode ser dispensado da exigência do código de acesso, mediante registro da característica no cadastro pela agência. Em conta conjunta, a dispensa vale só para o titular com a deficiência.

b) **Tipos:** CAA (letras), CAS (sílabas), CAN (alfanumérico). Emitido quando o cliente usa a TAA com cartão pela primeira vez, tentando uma transação/consulta — o cliente é avisado do novo código, que substitui o anterior.

c) Se o cliente disser que não tem/não anotou o código: oriente conforme a tabela abaixo, ou informe que TAAs com biometria dispensam o código de acesso (rotina 50132, itens 1 e 9).

**5.1. O que é:** código aleatório (letras, sílabas e/ou números), não escolhido pelo cliente; para PF e PJ, correntistas, não correntistas e poupadores portadores de cartão; necessário em: TAA, Banco 24 Horas e rede compartilhada (Banco Parceiro Beta).

**5.2. Cadastramento:** gerado e impresso automaticamente no primeiro uso do cartão na TAA; regenerado em migração de conta (mesmo cartão) ou quando o código antigo é cancelado. Se a impressora estiver inoperante, é mostrado só em tela. Código único para todos os titulares solidários.

**5.3. Alteração:** não existe alteração direta — o código deve ser cancelado (canais abaixo); a nova combinação é gerada automaticamente no próximo acesso à TAA. *(O código não muda se a senha da conta corrente for alterada.)*

| Canal | Procedimento |
|---|---|
| App Alfa | Área logada > Perfil > Segurança > Central de senhas > Código de Acesso > Solicitar novo código. |
| Site institucional | Área logada — confirmação via Alfa Code; sem Alfa Code, confirma na TAA com biometria cadastrada há mais de 7 dias. |
| Agência | Com a senha de 6 dígitos (recomendar levar o cartão). |

**5.4. Bloqueio:** após 3 tentativas seguidas incorretas. Bloqueio da senha de 6 dígitos ou do código de acesso mantém o uso da TAA com biometria. Bloqueio da senha de 6 dígitos mantém o uso do código de acesso, exceto nos bloqueios "U" ou "8".

**5.5. Desbloqueio:** pelo próprio cliente na TAA, usando o próprio código de acesso. Se houver novo erro, o código deve ser cancelado (site institucional com Alfa Code, App Alfa, ou qualquer agência) para gerar um novo.

---

## 6. Geração de Senha PF – Procedimentos

Envio de senha (6 e 8 dígitos) por SMS para PF — só para ALTERAÇÃO (não para cadastro de primeira senha, que segue outros canais). Não disponível para senhas "não cadastradas"/"a cadastrar" ou bloqueio "U". Faça as consultas do item 6.2 antes.

### 6.1. Atendimento

| Frente | Quem atende | Identificação |
|---|---|---|
| SAC QP | Correntistas e não correntistas | Cliente autenticado (URA, Token ou Identificação Positiva) |
| SAC QC | Não correntistas portadores de cartão (correntistas/poupadores: transferir para a Célula de Segurança via rotina 50106) | — |
| Plataforma de Relacionamento QP | Correntistas e não correntistas | Autenticado por CPF+senha, agência/conta+senha ou Token: IP dispensada. Atendimentos ATA, Consultoria e Texto: exigem IP. Bancada Cartão: Checklist Maior Risco. |
| Plataforma de Relacionamento QC | Não correntistas portadores de cartão (correntistas/poupadores: demais canais, itens 3 e 4) | — |

### 6.2. Consultas

1. Verifique o cadastro da senha em `SISRET X69 > 02` ou pela Plataforma (Segurança > Senhas > Gerenciamento de Senhas) — correntistas: agência/conta; não correntistas: número do cartão (não pedir validade/CVV; usar mês/ano do contato e "000" no CVV2).
2. Resultado "Não cadastrada"/"A cadastrar" → cliente não correntista com entrada via onboarding digital; não é possível enviar senha; oriente: 8 dígitos via App Alfa (se dispositivo autorizado com Alfa Code/push); 6 dígitos, comparecer a uma agência.
3. Resultado "U Bloqueado" → SAC Receptivo (Célula de Segurança) → rotina 50130; SAC Soluções QP → rotina 50131; SAC Receptivo QC → rotina 50112; Plataforma de Relacionamento → orientar contato com o SAC.
4. Demais situações → prossiga: pergunte o celular atual do cliente (não informe outros números cadastrados) e confira no cadastro (agência/conta ou MCI) se é o mesmo já registrado. Se divergente, ou se houver mais de um número/duplicidade cadastrada → oriente comparecimento a uma agência. Se for o mesmo e único número → siga para 6.3.

### 6.3. Geração de Senha

a) Acesse Plataforma > Segurança > Senhas > Envio de Senha por SMS.
b) Consulte por tipo de cliente: correntista (CPF, agência e conta, ou MCI); não correntista (CPF); na aba Cartão, informe o número (via `Cartão > 11 > 1` ou `17 > 01 > 01`) — se houver mais de um cartão, peça modalidade e os 4 últimos dígitos.
c) Selecione a conta/cartão do cliente.
d) Selecione o envio de senha de 8 e/ou 6 dígitos — o sistema gera uma senha aleatória e envia por SMS.
e) Informe que a senha chega por SMS ao celular cadastrado, sem prazo de expiração, e que deve ser alterada assim que possível por segurança.
f) Se for senha de 6 dígitos, informe que, após a alteração, é preciso validar o chip do cartão em qualquer TAA — caso contrário, a nova senha não funcionará com o cartão com chip.

---

## 7. Cliente no Exterior

a) **Central de Senhas** (no App Alfa; exige cartão ativo, dispositivo liberado e Alfa Code/Push): permite alterar/bloquear/desbloquear/criar senha de 8 dígitos; alterar/bloquear/desbloquear senha de 6 dígitos; solicitar novo código de acesso. Acesso com a senha atual: área logada > Perfil > Central de senhas. Sem a senha: tela inicial não logada > Recuperar senha.

b) **Agências no exterior:** procedimento de senhas disponível somente na agência de Tóquio.

c) Solicitar a um representante legal (com procuração com firma reconhecida) que realize a operação na agência de relacionamento do cliente no Brasil.

d) A agência de relacionamento envia ao e-mail cadastrado no MCI uma declaração para o cliente assinar e digitalizar — válido apenas para senhas bloqueadas por erro, não para bloqueio "U" (suspeita de fraude). O pedido pode começar por qualquer canal de contato, mas a declaração assinada só pode retornar pelo e-mail cadastrado no MCI. A agência de relacionamento pode ser confirmada com o cliente durante a ligação, na aba lateral da Plataforma de Relacionamento.

e) **Cartões com chip:** após a alteração da senha de 6 dígitos, oriente o cliente a atualizar o chip de todos os plásticos ao voltar ao Brasil (em uma TAA), sob risco de impacto em transações presenciais; carteiras digitais funcionam normalmente após a troca.

f) **Uso da senha no exterior:** alguns terminais usam PIN de 4 e/ou 6 dígitos. Nos de 4 dígitos, o cliente informa os 4 primeiros dígitos da sua senha de 6. No exterior, o cliente tem as mesmas opções dos demais clientes, pelo site institucional ou pelo App Alfa.

---

## 8. Senha do Portador Adicional

| Portador | Solicitação | Alteração/reposição |
|---|---|---|
| **Adicional não correntista** | Presencial: senha de 6 dígitos cadastrada na hora. Demais canais: senha enviada por correio ao endereço do portador titular. | Se perder, esquecer ou não receber, cadastrar nova em qualquer agência. |
| **Adicional correntista** | Usa a mesma senha pessoal de 6 dígitos de sua própria conta. Sem senha gravada: modalidades Doméstico/Internacional → sistema não gera o cartão; modalidades Gold e superiores → senha enviada por correio, cartão gerado após o recebimento. | Se perder, esquecer ou não receber, seguir as orientações do item 3. |

---

## 9. Acesso ao gov.br com credenciais do Banco Alfa

Ver rotina 50135.

---

## 10. Central de Senhas PF

Solução de segurança no App Alfa para o cliente gerenciar suas senhas.
- **Área logada:** Perfil > Segurança > Central de Segurança > Central de senhas; Perfil > Segurança > Central de senhas; Menu > Segurança > Central de Segurança > Central de Senhas.
- **Área não logada:** Tela inicial > Recuperar Senha; ou role a tela para cima > Recuperar Senha.

**Requisitos:** celular autorizado há mais de 30 dias; telefone cadastrado no ATO; Alfa Code ou Push habilitado; geolocalização ativa e autorizada; permissão de câmera concedida ao app; cartão ativo.

> **Atenção:** não correntistas usam a Central de Senhas apenas para alterar a senha "Conta de Acesso" (ver item 4.2.2).

---

## 11. Fontes de informação

UGS – Unidade de Gestão de Segurança (código 800040) · Normativo interno 5001 · Normativo interno 5002

---

## 12. Rotinas absorvidas

O conteúdo das seguintes rotinas foi absorvido por este documento:

| Código (anonimizado) | Assunto |
|---|---|
| 50137 | Senhas – Orientações (Código de Acesso) |
| 50138 | Senhas – Orientações (Não correntista) |
| 50139 | Senhas – Correntistas (Internet e Celular) |
| 50140 | Arquivada – Senhas – Orientações (Conta-corrente) |
| 50141 | POP UP – Senhas – Tipos de bloqueio |
| 50142 | Modalidade de conta simplificada – Senhas |
| 50143 | Senhas – Orientações – Poupador não correntista |
| 50144 | Acesso do cliente à plataforma digital gov.br (parceria Banco Alfa e Governo Federal) |
| 50145 | Senhas – Alfa Digital PJ |
| 50146 | Atendimento para clientes não participantes do modelo ATA |
| 50147 | Geração de senha PF – Procedimentos |
