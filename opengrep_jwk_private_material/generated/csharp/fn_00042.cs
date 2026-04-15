using Microsoft.IdentityModel.Tokens;
public class Fixture {
  public void Run() {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"v3fgUUEFkoMl","alg":"RS256","n":"o-Id5PDCURYH6h9yVeu2PCx6Ws23o6YVz9v6jln0Iz69FGsm","e":"AQAB"}
    var jwk = "{\"kty\":\"RSA\",\"kid\":\"v3fgUUEFkoMl\",\"alg\":\"RS256\",\"n\":\"o-Id5PDCURYH6h9yVeu2PCx6Ws23o6YVz9v6jln0Iz69FGsm\",\"e\":\"AQAB\"}";
    var key = new JsonWebKey(jwk);
  }
}
