using Microsoft.IdentityModel.Tokens;
public class Fixture {
  public void Run() {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"7PeJgIec1sYS","alg":"RS256","n":"rbobLPK66_axmdM0EDzzW2ex5wCByrx3GTOBN5wCWBfSdJXc","e":"AQAB"}
    var jwk = "{\"kty\":\"RSA\",\"kid\":\"7PeJgIec1sYS\",\"alg\":\"RS256\",\"n\":\"rbobLPK66_axmdM0EDzzW2ex5wCByrx3GTOBN5wCWBfSdJXc\",\"e\":\"AQAB\"}";
    var key = new JsonWebKey(jwk);
  }
}
